from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json
import math

import numpy as np
import pandas as pd

from data_contracts import read_csv_safe, ensure_campaign_frame
from eso_baseline import load_validated_snapshots, fit_empirical_sales_curve
from project_config import load_config as load_project_config, flat_context
from experiment_protocol import build_experiment_plan
from market_context import get_market
from lightweight_ml import LightweightEnsemble

ZONE_PRIORS = [
    {"area": "ESO / Forschungszentrum", "weight": 1.00, "why": "Venue + research campus + immediate catchment"},
    {"area": "Garching / Hochbrueck", "weight": 1.00, "why": "Local catchment + direct U6 access"},
    {"area": "Studentenstadt / Freimann", "weight": 1.00, "why": "Direct U6 corridor + younger adult audience"},
    {"area": "Universitaet / Schwabing", "weight": 1.00, "why": "Culture / music / university audience"},
]
AGE_PRIORS = {"20-34": 1.00, "35-49": 1.00, "50-60": 1.00}
CREATIVE_PRIORS = {"SXSW proof": 1.00, "Music + 360 experience": 1.00, "Four Tuesdays / scarcity": 1.00}
PLANNING_PRIOR = load_project_config()["planning_prior"]
CHANNEL_PRIORS = {channel: {"cpc": float(PLANNING_PRIOR["cpc_eur"]), "purchase_rate": float(PLANNING_PRIOR["incremental_tickets_per_click"])} for channel in ("Meta", "Google Search", "Retargeting")}
DATE_WEIGHTS = {}


@dataclass
class MarketingModelBundle:
    mode: str
    model: Optional[LightweightEnsemble]
    features: list[str]
    target: str
    rows: int
    mae: Optional[float] = None
    r2: Optional[float] = None
    operational: bool = False
    notes: str = ""

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            return np.zeros(len(X), dtype=float)
        return np.maximum(0.0, self.model.predict(X))


def load_config() -> dict:
    return flat_context(load_project_config())


def load_campaign_history(path: str | Path = "data/campaign_history.csv") -> pd.DataFrame:
    return ensure_campaign_frame(read_csv_safe(path))


def load_resolution_sales(path: str | Path = "data/eso_sales_snapshots.csv") -> pd.DataFrame:
    df = read_csv_safe(path)
    if df.empty:
        return df
    for c in ["available_seats", "capacity", "tickets_sold"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "collected_at_utc" in df.columns:
        df["collected_at"] = pd.to_datetime(df["collected_at_utc"], errors="coerce", utc=True)
    if "show_date" in df.columns:
        df["show_dt"] = pd.to_datetime(df["show_date"], errors="coerce", utc=True)
    if {"collected_at", "show_dt"}.issubset(df.columns):
        df["days_to_event"] = (df["show_dt"] - df["collected_at"]).dt.total_seconds() / 86400.0
    return df


def empirical_baseline() -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    snapshots = load_validated_snapshots()
    curve, stats = fit_empirical_sales_curve(snapshots)
    return curve, stats, snapshots


def _status_model(name_prefix: str) -> dict:
    p = Path("data/training_status.json")
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    for m in payload.get("models", []):
        if str(m.get("name", "")).lower().startswith(name_prefix.lower()):
            return m
    return {}


def load_marketing_model() -> MarketingModelBundle:
    status = _status_model("Ticket-lift")
    rows = int(status.get("rows", 0) or 0)
    path = Path(status.get("model_path") or "models/ticket_lift_response_lightweight.json")
    operational = bool(status.get("operational", False)) and str(status.get("status", "")).lower() == "trained"
    if operational and path.exists():
        try:
            model = LightweightEnsemble.load(path)
            return MarketingModelBundle(
                "Trained ticket-lift ML", model, list(status.get("features", [])), str(status.get("target", "")), rows,
                mae=status.get("mae"), r2=status.get("r2"), operational=True,
                notes="Uses only verified ticket attribution / controlled lift labels.",
            )
        except Exception as exc:
            return MarketingModelBundle("Prior only", None, [], "", rows, notes=f"Ticket model could not load: {exc}")
    return MarketingModelBundle(
        "Planning prior", None, list(status.get("features", [])), str(status.get("target", "")), rows,
        mae=status.get("mae"), r2=status.get("r2"), operational=False,
        notes=status.get("notes") or "Ticket-lift ML is intentionally inactive until verified labels exist and validation passes.",
    )


def train_marketing_ensemble(history: Optional[pd.DataFrame] = None, seed: int = 42) -> MarketingModelBundle:
    # Backward-compatible name used by the Streamlit page. Training is centralized in train_models.py.
    return load_marketing_model()


def _prior_cell_tickets(spend: float, area: str, age_band: str, channel: str, creative: str) -> float:
    spend = max(0.0, float(spend))
    if spend <= 0:
        return 0.0
    cp = CHANNEL_PRIORS.get(channel, CHANNEL_PRIORS["Meta"])
    zone_w = next((z["weight"] for z in ZONE_PRIORS if z["area"] == area), 1.0)
    age_w = AGE_PRIORS.get(age_band, 1.0)
    creative_w = CREATIVE_PRIORS.get(creative, 1.0)
    raw = (spend / cp["cpc"]) * cp["purchase_rate"] * zone_w * age_w * creative_w
    saturation = 1.0 / (1.0 + max(0.0, spend - 75.0) / 450.0)
    return max(0.0, raw * saturation)


def _model_row(spend: float, area: str, age: str, channel: str, creative: str, days_to_event: int, model: MarketingModelBundle) -> pd.DataFrame:
    data = {"spend_eur": spend, "days_to_event": days_to_event, "area": area, "age_band": age, "channel": channel, "creative": creative}
    return pd.DataFrame([{f: data.get(f, "Unknown") for f in model.features}])


def scenario_grid(test_spend: float = 50.0, model: Optional[MarketingModelBundle] = None, days_to_event: int = 30, market: dict | None = None) -> pd.DataFrame:
    model = model or load_marketing_model()
    rows = []
    market = market or get_market()
    zone_priors = [{"area": z["area"], "weight": 1.0, "why": z.get("why", "Selected market test zone")} for z in market.get("zones", [])] or ZONE_PRIORS
    for z in zone_priors:
        for age in AGE_PRIORS:
            for channel in CHANNEL_PRIORS:
                for creative in CREATIVE_PRIORS:
                    prior = _prior_cell_tickets(test_spend, z["area"], age, channel, creative)
                    if model.operational and model.model is not None:
                        pred = float(model.predict(_model_row(test_spend, z["area"], age, channel, creative, days_to_event, model))[0])
                        # Preserve a small prior anchor because samples will stay small for this one campaign.
                        ml_weight = min(0.90, max(0.60, 0.60 + max(0, model.rows - 18) / 100))
                        expected = ml_weight * pred + (1 - ml_weight) * prior
                        basis = f"Verified ticket-lift ML ({ml_weight:.0%}) + prior anchor"
                        uncertainty = max(1.0, float(model.mae or 3.0))
                    else:
                        expected = prior
                        basis = "Pre-campaign planning prior — test, not learned winner"
                        uncertainty = max(1.5, expected * 0.45)
                    rows.append({
                        "area": z["area"], "age_band": age, "channel": channel, "creative": creative,
                        "spend_eur": float(test_spend), "days_to_event": int(days_to_event), "prior_tickets": prior,
                        "predicted_extra_tickets": max(0.0, expected), "prediction_basis": basis,
                        "uncertainty_tickets": uncertainty, "why": z["why"],
                    })
    df = pd.DataFrame(rows)
    df["predicted_cpa"] = np.where(df["predicted_extra_tickets"] > 0, df["spend_eur"] / df["predicted_extra_tickets"], np.inf)
    df["low_extra"] = np.maximum(0, df["predicted_extra_tickets"] - 1.28 * df["uncertainty_tickets"])
    df["high_extra"] = df["predicted_extra_tickets"] + 1.28 * df["uncertainty_tickets"]
    return df.sort_values(["predicted_extra_tickets", "predicted_cpa"], ascending=[False, True]).reset_index(drop=True)


def _cell_prediction(spend: float, row: pd.Series, model: MarketingModelBundle, days_to_event: int) -> float:
    if spend <= 0:
        return 0.0
    prior = _prior_cell_tickets(spend, row["area"], row["age_band"], row["channel"], row["creative"])
    if model.operational and model.model is not None:
        pred = float(model.predict(_model_row(spend, row["area"], row["age_band"], row["channel"], row["creative"], days_to_event, model))[0])
        ml_weight = min(0.90, max(0.60, 0.60 + max(0, model.rows - 18) / 100))
        return max(0.0, ml_weight * pred + (1 - ml_weight) * prior)
    return prior


def optimize_budget(total_budget: float, model: Optional[MarketingModelBundle] = None, days_to_event: int = 30, increment: float = 25.0, max_cell_share: float = 0.40, top_cells: int = 18, market: dict | None = None) -> pd.DataFrame:
    model = model or load_marketing_model()
    total_budget = max(0.0, float(total_budget))
    if total_budget <= 0:
        return pd.DataFrame()
    if not model.operational:
        # A numerical optimiser would manufacture a winner from equal, unmeasured
        # priors. Before lift evidence exists, only the precommitted learning plan
        # can be allocated; the rest is explicitly reserved.
        plan = build_experiment_plan(market or get_market())
        remaining = min(total_budget, float(load_project_config()["marketing"]["experiment_budget_eur"]))
        rows = []
        for _, item in plan.iterrows():
            spend = min(remaining, float(item.get("planned_spend_eur", 0)))
            if spend <= 0:
                continue
            remaining -= spend
            row = {"area": item["area"], "age_band": item["age_band"], "channel": item["channel"], "creative": item["creative"]}
            prior = _prior_cell_tickets(spend, row["area"], row["age_band"], row["channel"], row["creative"])
            rows.append({**row, "budget_eur": spend, "expected_extra_tickets": prior,
                         "expected_cpa": spend / prior if prior else np.inf,
                         "prediction_basis": "Unverified planning scenario; reserve unallocated"})
            if remaining <= 0:
                break
        return pd.DataFrame(rows)
    grid = scenario_grid(test_spend=50, model=model, days_to_event=days_to_event, market=market).head(top_cells).copy()
    allocations = {i: 0.0 for i in grid.index}
    steps = int(round(total_budget / increment))
    max_cell = max(increment, total_budget * max_cell_share)
    for _ in range(steps):
        best_i, best_marginal = None, 0.0
        for i, row in grid.iterrows():
            current = allocations[i]
            if current + increment > max_cell + 1e-9:
                continue
            before = _cell_prediction(current, row, model, days_to_event)
            after = _cell_prediction(current + increment, row, model, days_to_event)
            marginal = after - before
            if marginal > best_marginal:
                best_i, best_marginal = i, marginal
        if best_i is None:
            break
        allocations[best_i] += increment
    rows = []
    for i, spend in allocations.items():
        if spend <= 0:
            continue
        r = grid.loc[i]
        expected = _cell_prediction(spend, r, model, days_to_event)
        rows.append({
            "area": r["area"], "age_band": r["age_band"], "channel": r["channel"], "creative": r["creative"],
            "budget_eur": spend, "expected_extra_tickets": expected,
            "expected_cpa": spend / expected if expected > 0 else np.inf,
            "prediction_basis": "Operational ML" if model.operational else "Scenario prior — do not treat as optimized winner",
        })
    out = pd.DataFrame(rows)
    return out.sort_values(["expected_extra_tickets", "expected_cpa"], ascending=[False, True]).reset_index(drop=True) if not out.empty else out


def next_increment_scenarios(allocation: pd.DataFrame, increment: float = 25.0, model: Optional[MarketingModelBundle] = None, days_to_event: int = 30) -> pd.DataFrame:
    """Marginal response for one extra spend increment, with provenance."""
    model = model or load_marketing_model()
    if allocation is None or allocation.empty:
        return pd.DataFrame()
    rows = []
    for _, cell in allocation.iterrows():
        before = float(cell["budget_eur"])
        after = before + increment
        marginal = _cell_prediction(after, cell, model, days_to_event) - _cell_prediction(before, cell, model, days_to_event)
        rows.append({"area": cell["area"], "channel": cell["channel"], "age_band": cell["age_band"],
                     "creative": cell["creative"], "next_eur": increment, "scenario_extra_tickets": round(max(0.0, marginal), 2),
                     "basis": "Controlled lift ML" if model.operational else "Unverified prior; do not use as winner evidence"})
    return pd.DataFrame(rows).sort_values("scenario_extra_tickets", ascending=False).reset_index(drop=True)


def _baseline_params(cfg: dict, emp_stats: dict) -> tuple[float, float]:
    if emp_stats and emp_stats.get("unique_shows", 0) >= 6:
        fill = float(emp_stats.get("day0_fill_base", 0.36))
        unc = float(emp_stats.get("baseline_uncertainty", 0.30))
    else:
        fill, unc = 0.36, 0.32
    return float(np.clip(fill, 0.05, 0.95)), float(np.clip(unc, 0.12, 0.50))


def hybrid_simulation(budget: float, model: Optional[MarketingModelBundle] = None, cfg: Optional[dict] = None, emp_stats: Optional[dict] = None, days_to_event: int = 30, n: int = 10000, seed: int = 42, market: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    model = model or load_marketing_model()
    cfg = cfg or load_config()
    emp_stats = emp_stats or {}
    capacity = int(cfg.get("capacity_per_show", 109))
    dates = cfg.get("show_dates", [])
    total_capacity = capacity * len(dates)
    baseline_fill, baseline_unc = _baseline_params(cfg, emp_stats)
    allocation = optimize_budget(budget, model=model, days_to_event=days_to_event, market=market)
    expected_lift = float(allocation["expected_extra_tickets"].sum()) if not allocation.empty else 0.0
    if model.operational:
        lift_sd = max(float(model.mae or 2.5) * math.sqrt(max(1, len(allocation))), expected_lift * 0.20)
    else:
        lift_sd = max(5.0, expected_lift * 0.50)
    rng = np.random.default_rng(seed)
    weights = np.array([DATE_WEIGHTS.get(str(d), 1.0) for d in dates], dtype=float)
    if len(weights):
        weights = weights / weights.mean()
    rows = []
    for _ in range(n):
        baseline_by_show = []
        for w in weights:
            pct = rng.normal(baseline_fill * w, baseline_fill * baseline_unc)
            baseline_by_show.append(int(round(capacity * float(np.clip(pct, 0.05, 0.94)))))
        baseline_total = int(sum(baseline_by_show))
        lift = max(0.0, rng.normal(expected_lift, lift_sd))
        remaining = max(0, total_capacity - baseline_total)
        lift = min(remaining, lift * (0.72 + 0.28 * remaining / max(1, total_capacity)))
        total = int(min(total_capacity, round(baseline_total + lift)))
        rows.append({
            "baseline_tickets": baseline_total, "incremental_tickets": total - baseline_total,
            "total_tickets": total, "occupancy_pct": 100 * total / max(1, total_capacity),
            "incremental_cpa": budget / (total - baseline_total) if total > baseline_total and budget > 0 else np.inf,
        })
    return pd.DataFrame(rows), allocation


def budget_forecast_curve(max_budget: int = 1000, step: int = 50, model: Optional[MarketingModelBundle] = None, cfg: Optional[dict] = None, emp_stats: Optional[dict] = None, days_to_event: int = 30, market: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    capacity = int(cfg.get("capacity_per_show", 109)) * len(cfg.get("show_dates", []))
    rows = []
    for b in range(0, max_budget + 1, step):
        # Common random numbers make spend differences reflect allocation, not noise.
        sim, _ = hybrid_simulation(b, model=model, cfg=cfg, emp_stats=emp_stats, days_to_event=days_to_event, n=2000, seed=1000, market=market)
        rows.append({
            "budget_eur": b,
            "low_tickets": float(sim["total_tickets"].quantile(0.10)),
            "base_tickets": float(sim["total_tickets"].quantile(0.50)),
            "high_tickets": float(sim["total_tickets"].quantile(0.90)),
            "extra_tickets": float(sim["incremental_tickets"].median()),
            "p50": 100 * float((sim["total_tickets"] >= capacity * 0.50).mean()),
            "p60": 100 * float((sim["total_tickets"] >= capacity * 0.60).mean()),
            "p75": 100 * float((sim["total_tickets"] >= capacity * 0.75).mean()),
            "p90": 100 * float((sim["total_tickets"] >= capacity * 0.90).mean()),
            "p100": 100 * float((sim["total_tickets"] >= capacity).mean()),
        })
    return pd.DataFrame(rows)


def per_show_forecast(sim: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    dates = cfg.get("show_dates", [])
    capacity = int(cfg.get("capacity_per_show", 109))
    weights = np.array([DATE_WEIGHTS.get(str(d), 1.0) for d in dates], dtype=float)
    weights = weights / weights.sum() if len(weights) else weights
    q10, q50, q90 = [float(sim["total_tickets"].quantile(q)) for q in (0.10, 0.50, 0.90)]
    rows = []
    for d, w in zip(dates, weights):
        rows.append({"show_date": d, "low": min(capacity, round(q10 * w)), "base": min(capacity, round(q50 * w)), "high": min(capacity, round(q90 * w))})
    return pd.DataFrame(rows)


def model_readiness(history: pd.DataFrame, snapshots: pd.DataFrame, emp_stats: dict) -> dict:
    history = history if history is not None else pd.DataFrame()
    snapshots = snapshots if snapshots is not None else pd.DataFrame()
    rows = len(snapshots)
    unique_shows = int(emp_stats.get("unique_shows", 0)) if emp_stats else 0
    repeated = int(emp_stats.get("repeated_shows", 0)) if emp_stats else 0
    lead_span = max(0, int(emp_stats.get("max_days_to_event", 0)) - int(emp_stats.get("min_days_to_event", 0))) if emp_stats else 0
    campaign_rows = len(history)
    areas = int(history["area"].replace("", pd.NA).dropna().nunique()) if "area" in history.columns else 0
    channels = int(history["channel"].replace("", pd.NA).dropna().nunique()) if "channel" in history.columns else 0
    creatives = int(history["creative"].replace("", pd.NA).dropna().nunique()) if "creative" in history.columns else 0
    baseline_score = min(25, rows / 4) + min(15, unique_shows * 1.5) + min(10, repeated * 2)
    marketing_score = min(25, campaign_rows * 0.7) + min(10, areas * 2.5) + min(8, channels * 3) + min(7, creatives * 2)
    score = int(round(min(100, baseline_score + marketing_score)))
    model = load_marketing_model()
    if model.operational:
        stage = "Verified ticket-lift ML active"
    elif campaign_rows:
        stage = "Campaign learning in progress"
    elif unique_shows >= 6:
        stage = "Empirical ESO baseline + experiment-ready"
    else:
        stage = "Baseline collection"
    return {"score": score, "stage": stage, "campaign_rows": campaign_rows, "unique_shows": unique_shows, "repeated_shows": repeated, "areas": areas, "channels": channels, "creatives": creatives, "lead_span": lead_span}


def resolution_pace_forecast(resolution: pd.DataFrame, curve: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    if resolution is None or resolution.empty or curve is None or curve.empty:
        return pd.DataFrame()
    work = resolution.copy()
    if "status" in work.columns:
        work = work[work["status"].astype(str).str.startswith("ok")]
    work = work.dropna(subset=["tickets_sold", "capacity", "days_to_event"])
    if work.empty:
        return pd.DataFrame()
    if "collected_at" in work.columns:
        work = work.sort_values("collected_at")
    key = "url" if "url" in work.columns else "show_date"
    work = work.drop_duplicates(key, keep="last")
    days_grid = curve["days_to_event"].to_numpy(dtype=float)
    baseline_pct = curve["base_sold_pct"].to_numpy(dtype=float) / 100.0
    baseline_final = max(0.05, float(baseline_pct[-1]))
    rows = []
    for _, r in work.iterrows():
        d = float(r["days_to_event"])
        current_frac = float(r["tickets_sold"] / r["capacity"])
        expected_now = float(np.interp(d, days_grid[::-1], baseline_pct[::-1], left=baseline_pct[-1], right=baseline_pct[0]))
        pace_ratio = float(np.clip(current_frac / max(0.02, expected_now), 0.45, 1.75))
        projected_frac = float(np.clip(baseline_final * pace_ratio, current_frac, 0.99))
        rows.append({
            "show_date": str(r.get("show_date", "")), "days_to_event": round(d, 1),
            "tickets_sold_now": int(r["tickets_sold"]), "baseline_expected_now": round(expected_now * float(r["capacity"]), 1),
            "pace_index": round(pace_ratio * 100, 0), "projected_final_tickets": int(round(float(r["capacity"]) * projected_frac)),
        })
    return pd.DataFrame(rows)

