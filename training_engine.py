from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
import json

import numpy as np
import pandas as pd

from data_contracts import ensure_campaign_frame, read_csv_safe
from eso_baseline import load_validated_snapshots, fit_empirical_sales_curve
from lightweight_ml import (
    LightweightEnsemble,
    cv_predict,
    feature_importance_from_weights,
    fit_bootstrap_ridge_ensemble,
    regression_metrics,
)
from project_config import load_config
from experiment_protocol import build_experiment_plan

MODEL_DIR = Path("models")
DATA_DIR = Path("data")
STATUS_PATH = DATA_DIR / "training_status.json"
HISTORY_PATH = DATA_DIR / "training_history.csv"


@dataclass
class TrainResult:
    name: str
    status: str
    rows: int
    target: str = ""
    features: list[str] | None = None
    mae: Optional[float] = None
    mae_seats: Optional[float] = None
    rmse_pp: Optional[float] = None
    r2: Optional[float] = None
    benchmark_mae: Optional[float] = None
    benchmark_r2: Optional[float] = None
    validation_mode: str = ""
    model_path: str = ""
    operational: bool = False
    notes: str = ""

    def to_dict(self):
        d = asdict(self)
        d["features"] = d["features"] or []
        return d


def _cv_splits(n: int, groups: int | None = None) -> int:
    if groups is not None:
        if groups < 3:
            return 0
        return min(5, groups)
    if n < 8:
        return 0
    if n < 15:
        return 3
    if n < 30:
        return 4
    return 5


def _group_folds(groups: pd.Series, folds: int, seed: int) -> list[tuple[np.ndarray, np.ndarray]]:
    g = groups.fillna("Unknown").astype(str).reset_index(drop=True)
    unique = np.asarray(g.unique().tolist(), dtype=object)
    rng = np.random.default_rng(seed)
    rng.shuffle(unique)
    chunks = np.array_split(unique, max(2, min(folds, len(unique))))
    out = []
    for chunk in chunks:
        mask = g.isin(list(chunk)).to_numpy()
        te = np.where(mask)[0]
        tr = np.where(~mask)[0]
        if len(tr) >= 5 and len(te) > 0:
            out.append((tr, te))
    return out


def _group_cv_predict(X: pd.DataFrame, y: pd.Series, groups: pd.Series, numeric: list[str], categorical: list[str], target: str, seed: int):
    folds = _cv_splits(len(y), groups.astype(str).nunique())
    if folds < 3:
        return None
    pred = np.full(len(y), np.nan, dtype=float)
    for i, (tr, te) in enumerate(_group_folds(groups, folds, seed)):
        model = fit_bootstrap_ridge_ensemble(
            X.iloc[tr].reset_index(drop=True), y.iloc[tr].reset_index(drop=True),
            numeric, categorical, target, seed=seed + i + 1, n_models=21,
        )
        pred[te] = model.predict(X.iloc[te].reset_index(drop=True))
    return pred


def _empirical_cv_predict(df: pd.DataFrame, groups: pd.Series) -> np.ndarray:
    pred = np.full(len(df), np.nan, dtype=float)
    folds = _group_folds(groups, _cv_splits(len(df), groups.astype(str).nunique()), 41)
    for tr, te in folds:
        if len(tr) < 6 or len(te) == 0:
            continue
        curve, _ = fit_empirical_sales_curve(df.iloc[tr].reset_index(drop=True))
        if curve.empty:
            continue
        x = curve["days_to_event"].to_numpy(dtype=float)
        y = curve["base_sold_pct"].to_numpy(dtype=float)
        # curve is descending days; reverse for np.interp.
        pred[te] = np.interp(df.iloc[te]["days_to_event"].to_numpy(dtype=float), x[::-1], y[::-1], left=y[-1], right=y[0])
    return pred


def _fit_validate(X: pd.DataFrame, y: pd.Series, numeric: list[str], categorical: list[str], target: str, seed: int, groups: pd.Series | None = None):
    pred = None
    validation_mode = "row-wise CV"
    if groups is not None and groups.astype(str).nunique() >= 3:
        pred = _group_cv_predict(X.reset_index(drop=True), y.reset_index(drop=True), groups.reset_index(drop=True), numeric, categorical, target, seed)
        validation_mode = "grouped CV"
    if pred is None:
        folds = _cv_splits(len(y))
        if folds >= 3:
            pred = cv_predict(X.reset_index(drop=True), y.reset_index(drop=True), numeric, categorical, target, folds=folds, seed=seed)
    mae = r2 = None
    if pred is not None:
        ok = np.isfinite(pred)
        if ok.sum() >= 3:
            mae, r2 = regression_metrics(y.to_numpy(dtype=float)[ok], pred[ok])
    model = fit_bootstrap_ridge_ensemble(X.reset_index(drop=True), y.reset_index(drop=True), numeric, categorical, target, seed=seed, n_models=31)
    return model, mae, r2, validation_mode


def train_eso_demand_model(path: str | Path = "data/eso_comparable_snapshots.csv") -> TrainResult:
    cfg = load_config()
    df = load_validated_snapshots(path)
    if df.empty:
        return TrainResult("ESO demand model", "waiting", 0, notes="No validated ESO booking snapshots yet.")
    df["tickets_sold"] = pd.to_numeric(df["tickets_sold_so_far"], errors="coerce")
    df["capacity"] = pd.to_numeric(df["capacity"], errors="coerce")
    df["days_to_event"] = pd.to_numeric(df["days_to_event"], errors="coerce")
    df = df.dropna(subset=["days_to_event", "tickets_sold", "capacity"])
    df = df[(df["capacity"] > 0) & (df["tickets_sold"] >= 0)]
    df["sold_pct"] = 100.0 * df["tickets_sold"] / df["capacity"]

    # Programme family is useful for validation across showtimes, but an unseen title (Resolution)
    # falls back to Unknown. It is not treated as proof of causal similarity.
    df["programme_family"] = df["programme_title"].fillna("Unknown").astype(str).str.lower().str.replace(r"\s+-\s+with subtitles$", "", regex=True)
    numeric = [c for c in ["days_to_event", "start_hour", "month", "minimum_age", "ticket_price_eur", "duration_min"] if c in df.columns]
    categorical = [c for c in ["weekday", "programme_family"] if c in df.columns]
    features = numeric + categorical
    unique_leads = int(df["days_to_event"].nunique())
    unique_shows = int(df["show_key"].nunique())
    if len(df) < 10 or unique_leads < 4 or unique_shows < 6:
        return TrainResult(
            "ESO demand model", "collecting", len(df), target="sold_pct", features=features,
            notes=f"Have {len(df)} rows, {unique_shows} shows and {unique_leads} lead times. Keep daily collection running.",
        )

    X = df[features].copy()
    for c in categorical:
        X[c] = X[c].fillna("Unknown").astype(str)
    y = df["sold_pct"].astype(float)
    groups = df["show_key"].astype(str)
    model, mae, r2, validation_mode = _fit_validate(X, y, numeric, categorical, "sold_pct", seed=41, groups=groups)

    bench_pred = _empirical_cv_predict(df.reset_index(drop=True), groups.reset_index(drop=True))
    ok = np.isfinite(bench_pred)
    bmae = br2 = None
    if ok.sum() >= 3:
        bmae, br2 = regression_metrics(y.to_numpy(dtype=float)[ok], bench_pred[ok])

    # All reported errors use held-out booking groups. RMSE is in occupancy points.
    cv_pred = _group_cv_predict(X.reset_index(drop=True), y.reset_index(drop=True), groups.reset_index(drop=True), numeric, categorical, "sold_pct", 41)
    valid = np.isfinite(cv_pred) if cv_pred is not None else np.zeros(len(y), dtype=bool)
    rmse_pp = float(np.sqrt(np.mean((y.to_numpy()[valid] - cv_pred[valid]) ** 2))) if valid.any() else None
    mae_seats = float(np.mean(np.abs(y.to_numpy()[valid] - cv_pred[valid]) * df["capacity"].to_numpy()[valid] / 100)) if valid.any() else None

    gates = cfg.get("model_gates", {})
    max_mae = float(gates.get("operational_baseline_max_mae_pp", 12))
    min_r2 = float(gates.get("operational_baseline_min_r2", 0.0))
    # ML is only operational if it passes absolute quality AND beats the empirical benchmark.
    operational = bool(mae is not None and r2 is not None and mae <= max_mae and r2 >= min_r2 and (bmae is None or mae <= bmae))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    out = MODEL_DIR / "eso_demand_lightweight.json"
    model.meta.update({
        "rows": len(df), "unique_lead_times": unique_leads, "unique_shows": unique_shows,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(), "features": features,
        "validation_mode": validation_mode, "operational": operational,
        "benchmark_mae": bmae, "benchmark_r2": br2,
        "rmse_pp": rmse_pp, "mae_seats": mae_seats,
    })
    model.save(out)
    feature_importance_from_weights(model).to_csv(MODEL_DIR / "eso_demand_feature_importance.csv", index=False)
    status = "trained" if operational else "trained_low_confidence"
    notes = (
        "Operational ML selected because grouped validation passed the configured gate."
        if operational else
        "Model trained, but grouped-by-show validation is not strong enough for operational use. The dashboard uses the empirical PAVA baseline instead."
    )
    return TrainResult(
        "ESO demand model", status, len(df), target="sold_pct", features=features,
        mae=mae, mae_seats=mae_seats, rmse_pp=rmse_pp, r2=r2, benchmark_mae=bmae, benchmark_r2=br2,
        validation_mode=validation_mode, model_path=str(out), operational=operational, notes=notes,
    )


def _derive_engagement_targets(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in ["spend_eur", "impressions", "video_views_75", "clicks", "landing_page_views", "days_to_event"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    if "impressions" in out.columns:
        denom = out["impressions"].replace(0, np.nan)
        out["ctr_pct"] = 100.0 * pd.to_numeric(out.get("clicks"), errors="coerce") / denom
        out["vtr75_pct"] = 100.0 * pd.to_numeric(out.get("video_views_75"), errors="coerce") / denom
    if {"clicks", "landing_page_views"}.issubset(out.columns):
        out["lpv_per_click_pct"] = 100.0 * out["landing_page_views"] / out["clicks"].replace(0, np.nan)
    return out


def _marketing_features(df: pd.DataFrame, include_channel: bool = True):
    numeric = [c for c in ["spend_eur", "days_to_event"] if c in df.columns]
    cats = [c for c in ["city", "area", "age_band", "creative"] if c in df.columns]
    if include_channel and "channel" in df.columns:
        cats.insert(0, "channel")
    return numeric, cats


def _campaign_groups(df: pd.DataFrame) -> pd.Series:
    pieces = []
    for c in ["campaign_id", "adset_id", "test_id"]:
        if c in df.columns:
            pieces.append(df[c].fillna("").astype(str))
    fallback = pd.Series("", index=df.index, dtype=str)
    for c in ["channel", "city", "area", "age_band", "creative", "experiment_wave"]:
        if c in df.columns:
            fallback = fallback + "|" + df[c].fillna("").astype(str)
    if not pieces:
        return fallback
    out = pieces[0]
    for s in pieces[1:]:
        out = out + "|" + s
    out = out.where(out.str.replace("|", "", regex=False).str.len() > 0, fallback)
    return out


def train_engagement_model(path: str | Path = "data/campaign_history.csv") -> TrainResult:
    cfg = load_config()
    raw = ensure_campaign_frame(read_csv_safe(path))
    df = _derive_engagement_targets(raw)
    if df.empty:
        return TrainResult("Engagement-response model", "waiting", 0, notes="No campaign observations yet.")
    min_rows = int(cfg.get("model_gates", {}).get("engagement_min_rows", 12))
    target = ""
    for c in ["landing_page_views", "ctr_pct", "vtr75_pct"]:
        if c in df.columns and pd.to_numeric(df[c], errors="coerce").notna().sum() >= min_rows:
            target = c
            break
    if not target:
        return TrainResult("Engagement-response model", "collecting", len(df), notes=f"Need at least {min_rows} real daily/ad-set observations with engagement metrics.")

    areas = df["area"].replace("", pd.NA).dropna().nunique()
    ages = df["age_band"].replace("", pd.NA).dropna().nunique()
    creatives = df["creative"].replace("", pd.NA).dropna().nunique()
    channels = df["channel"].replace("", pd.NA).dropna().nunique()
    include_channel = channels >= 2
    numeric, categorical = _marketing_features(df, include_channel=include_channel)
    features = numeric + categorical
    usable = df.copy()
    usable[target] = pd.to_numeric(usable[target], errors="coerce")
    usable = usable.dropna(subset=[target])
    if len(usable) < min_rows or areas < 2 or creatives < 2:
        return TrainResult("Engagement-response model", "collecting", len(usable), target=target, features=features,
                           notes=f"Need >=2 areas and >=2 creatives. Current: {areas} areas, {creatives} creatives, {channels} channels.")
    for c in categorical:
        usable[c] = usable[c].fillna("Unknown").astype(str)
    X = usable[features].copy()
    y = usable[target].astype(float)
    groups = _campaign_groups(usable)
    if groups.nunique() < 3:
        return TrainResult("Engagement-response model", "collecting", len(usable), target=target, features=features, notes="Need at least three independent tests for grouped validation.")
    model, mae, r2, validation_mode = _fit_validate(X, y, numeric, categorical, target, seed=52, groups=groups)
    operational = bool(validation_mode == "grouped CV" and mae is not None and r2 is not None and r2 >= 0)
    out = MODEL_DIR / "engagement_response_lightweight.json"
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.meta.update({"rows": len(usable), "validation_mode": validation_mode, "trained_at_utc": datetime.now(timezone.utc).isoformat()})
    model.save(out)
    feature_importance_from_weights(model).to_csv(MODEL_DIR / "engagement_feature_importance.csv", index=False)
    return TrainResult("Engagement-response model", "trained" if operational else "trained_low_confidence", len(usable), target=target, features=features,
                       mae=mae, r2=r2, validation_mode=validation_mode, model_path=str(out), operational=operational,
                       notes="Predictive engagement only; never ticket lift. Grouped validation governs operational use.")


def _verified_ticket_target(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    out = df.copy()
    out["label_source"] = out.get("label_source", "").fillna("").astype(str).str.lower()
    for c in ["incremental_tickets_estimate", "tickets_attributed"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    # A tracked purchase is not necessarily an incremental purchase. Only controlled
    # incremental estimates can train a model named ticket lift.
    if "incremental_tickets_estimate" in out.columns:
        allowed = out["label_source"].isin(["controlled_residual", "staggered_test"])
        if out.loc[allowed, "incremental_tickets_estimate"].notna().sum() >= 1:
            return out[allowed].copy(), "incremental_tickets_estimate"
    return out.iloc[0:0].copy(), ""


def train_ticket_lift_model(path: str | Path = "data/campaign_history.csv") -> TrainResult:
    cfg = load_config()
    raw = ensure_campaign_frame(read_csv_safe(path))
    if raw.empty:
        return TrainResult("Ticket-lift model", "waiting", 0, notes="No campaign history yet.")
    df, target = _verified_ticket_target(raw)
    if not target:
        return TrainResult("Ticket-lift model", "waiting", len(raw), notes="No controlled incremental ticket estimates yet. Tracked purchases alone do not establish lift.")
    gates = cfg.get("model_gates", {})
    min_rows = int(gates.get("ticket_lift_min_rows", 18))
    min_areas = int(gates.get("ticket_lift_min_areas", 3))
    min_creatives = int(gates.get("ticket_lift_min_creatives", 2))
    numeric, categorical = _marketing_features(df, include_channel=True)
    features = numeric + categorical
    for c in numeric + [target]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in categorical:
        df[c] = df[c].fillna("Unknown").astype(str)
    df = df.dropna(subset=[target, "spend_eur"])
    areas = df["area"].replace("", pd.NA).dropna().nunique()
    creatives = df["creative"].replace("", pd.NA).dropna().nunique()
    if len(df) < min_rows or areas < min_areas or creatives < min_creatives:
        return TrainResult("Ticket-lift model", "collecting", len(df), target=target, features=features,
                           notes=f"Need {min_rows}+ verified labels across {min_areas}+ areas and {min_creatives}+ creatives. Current: {len(df)} rows, {areas} areas, {creatives} creatives.")
    X = df[features].copy()
    y = df[target].astype(float)
    groups = _campaign_groups(df)
    if groups.nunique() < 3:
        return TrainResult("Ticket-lift model", "collecting", len(df), target=target, features=features, notes="Need three independent campaign tests for grouped validation.")
    model, mae, r2, validation_mode = _fit_validate(X, y, numeric, categorical, target, seed=63, groups=groups)
    max_mae = float(gates.get("operational_marketing_max_mae_tickets", 5))
    operational = bool(validation_mode == "grouped CV" and mae is not None and r2 is not None and mae <= max_mae and r2 >= 0)
    out = MODEL_DIR / "ticket_lift_response_lightweight.json"
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.meta.update({"rows": len(df), "validation_mode": validation_mode, "trained_at_utc": datetime.now(timezone.utc).isoformat(), "operational": operational})
    model.save(out)
    feature_importance_from_weights(model).to_csv(MODEL_DIR / "ticket_lift_feature_importance.csv", index=False)
    status = "trained" if operational else "trained_low_confidence"
    return TrainResult("Ticket-lift model", status, len(df), target=target, features=features,
                       mae=mae, r2=r2, validation_mode=validation_mode, model_path=str(out), operational=operational,
                       notes="Only verified ticket labels are used. Low-confidence models remain visible but are not used to allocate budget automatically.")


def generate_active_learning_plan(path: str | Path = "data/experiment_plan.csv") -> pd.DataFrame:
    """Write the configured default city's complete EUR 240 learning plan."""
    plan = build_experiment_plan()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    plan.to_csv(p, index=False)
    return plan

def _append_training_history(results: list[TrainResult], trained_at: str) -> None:
    rows = []
    for r in results:
        rows.append({
            "trained_at_utc": trained_at, "model": r.name, "status": r.status, "rows": r.rows,
            "target": r.target, "mae": r.mae, "mae_seats": r.mae_seats, "rmse_pp": r.rmse_pp, "r2": r.r2, "benchmark_mae": r.benchmark_mae,
            "benchmark_r2": r.benchmark_r2, "validation_mode": r.validation_mode,
            "operational": r.operational, "model_path": r.model_path,
        })
    new = pd.DataFrame(rows)
    old = read_csv_safe(HISTORY_PATH)
    combined = pd.concat([old, new], ignore_index=True) if not old.empty else new
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(HISTORY_PATH, index=False)


def run_all_training() -> list[TrainResult]:
    results = [train_eso_demand_model(), train_engagement_model(), train_ticket_lift_model()]
    trained_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "trained_at_utc": trained_at,
        "backend": "reef-lightweight-ml-v2 (numpy/pandas; no scikit-learn)",
        "models": [r.to_dict() for r in results],
    }
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _append_training_history(results, trained_at)
    return results


def load_model(path: str | Path) -> LightweightEnsemble | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return LightweightEnsemble.load(p)
    except Exception:
        return None
