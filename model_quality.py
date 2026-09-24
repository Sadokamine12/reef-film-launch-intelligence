from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

from eso_baseline import load_validated_snapshots
from data_contracts import read_csv_safe

DATA_DIR = Path("data")
STATUS_PATH = DATA_DIR / "training_status.json"
HISTORY_PATH = DATA_DIR / "training_history.csv"


def load_status() -> dict:
    if not STATUS_PATH.exists():
        return {}
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def training_history(trusted_only: bool = True) -> pd.DataFrame:
    df = read_csv_safe(HISTORY_PATH)
    if df.empty or not trusted_only:
        return df
    # Earlier patch-era runs did not record their validation methodology and included
    # row-wise CV that can leak repeated snapshots from the same show. Keep those rows
    # on disk for audit, but exclude them from the professional quality chart.
    if "model" in df.columns and "validation_mode" in df.columns:
        eso = df["model"].astype(str).str.startswith("ESO demand")
        trusted_eso = df["validation_mode"].fillna("").astype(str).str.contains("grouped", case=False)
        df = df[(~eso) | trusted_eso].copy()
    return df


def eso_coverage() -> dict:
    df = load_validated_snapshots()
    if df.empty:
        return {"rows":0,"unique_shows":0,"repeated_shows":0,"observation_days":0,"lead_min":None,"lead_max":None,"lead_unique":0,"coverage_score":0,"buckets":pd.DataFrame(),"valid":df}
    show_counts = df.groupby("show_key")["snapshot_day"].nunique()
    unique_shows = int(show_counts.size)
    repeated = int((show_counts >= 2).sum())
    obs_days = int(df["snapshot_day"].replace("", pd.NA).dropna().nunique())
    lead = pd.to_numeric(df["days_to_event"], errors="coerce").dropna()
    bins = [-0.1, 7, 14, 30, 60, 181]
    labels = ["0–7 days", "8–14 days", "15–30 days", "31–60 days", "61+ days"]
    buckets = pd.cut(df["days_to_event"], bins=bins, labels=labels).value_counts().reindex(labels, fill_value=0).rename_axis("lead_window").reset_index(name="snapshots")
    score = 0
    score += min(30, int(len(df) / 100 * 30))
    score += min(20, int(unique_shows / 15 * 20))
    score += min(25, int(repeated / 10 * 25))
    score += int((buckets["snapshots"].gt(0).sum()) / 5 * 20)
    score += min(5, int(lead.nunique() / 20 * 5))
    return {
        "rows": int(len(df)), "unique_shows": unique_shows, "repeated_shows": repeated,
        "observation_days": obs_days, "lead_min": float(lead.min()) if len(lead) else None,
        "lead_max": float(lead.max()) if len(lead) else None, "lead_unique": int(lead.nunique()),
        "coverage_score": int(min(100, score)), "buckets": buckets, "valid": df,
    }


def current_model(prefix: str) -> dict:
    for m in load_status().get("models", []):
        if str(m.get("name", "")).lower().startswith(prefix.lower()):
            return m
    return {}


def current_eso_model() -> dict:
    return current_model("ESO demand")


def quality_label(model: dict, coverage_score: int) -> tuple[str, str]:
    status = str(model.get("status", ""))
    if not model:
        return "NOT TRAINED", "Run train_models.py."
    if bool(model.get("operational", False)):
        return "OPERATIONAL", "Validation passed the configured gate. Keep uncertainty bands visible."
    try:
        mae = float(model.get("mae"))
        r2 = float(model.get("r2"))
    except Exception:
        return "LOW CONFIDENCE", "The model exists but validation metrics are incomplete."
    if r2 < 0 or mae > 15:
        return "LOW CONFIDENCE", "Grouped validation is weak. Use the empirical baseline, not the ML adjustment."
    if r2 >= 0.3 and mae <= 12 and coverage_score >= 40:
        return "EARLY USEFUL", "The model is improving, but the empirical baseline remains the safer primary forecast until the operational gate passes."
    return "LOW CONFIDENCE", "Collect more repeated shows and broader lead-time coverage."


def confidence_summary(coverage: dict, model: dict, attribution: dict) -> dict[str, str]:
    """Ordinal evidence labels; never a fabricated probability of correctness."""
    shows = int(coverage.get("unique_shows", 0))
    repeated = int(coverage.get("repeated_shows", 0))
    near = coverage.get("lead_min") is not None and float(coverage["lead_min"]) <= 7
    mae = float(model.get("mae") or 999)
    if shows >= 30 and repeated >= 20 and mae <= 8:
        presale = "HIGH"
    elif shows >= 20 and repeated >= 12 and mae <= 12:
        presale = "GOOD"
    elif shows >= 15 and repeated >= 10 and mae <= 15:
        presale = "MODERATE"
    elif shows >= 10 and repeated >= 8 and mae <= 20:
        presale = "LOW"
    else:
        presale = "VERY LOW"
    final_sales = presale if near else "VERY LOW"
    lift = "MODERATE" if attribution.get("level") == "D" and int(attribution.get("verified_ticket_rows", 0)) >= 18 else "VERY LOW"
    return {"eso_presale": presale, "resolution_final": final_sales, "paid_lift": lift}


def next_data_actions(coverage: dict, model: dict) -> list[str]:
    actions = []
    if coverage["rows"] < 60:
        actions.append(f"Collect {60-coverage['rows']} more canonical booking snapshots to reach 60 rows.")
    if coverage["unique_shows"] < 15:
        actions.append(f"Track {15-coverage['unique_shows']} more unique booking IDs.")
    if coverage["repeated_shows"] < 8:
        actions.append(f"Revisit the same shows until {8-coverage['repeated_shows']} more shows have repeated-day observations.")
    missing = coverage.get("buckets", pd.DataFrame())
    if not missing.empty:
        empty = missing.loc[missing["snapshots"].eq(0), "lead_window"].astype(str).tolist()
        if empty:
            actions.append("Fill missing lead-time windows: " + ", ".join(empty) + ".")
    if not bool(model.get("operational", False)):
        actions.append("Keep the ML adjustment disabled operationally; the empirical curve remains the primary baseline until grouped validation passes.")
    return actions or ["Coverage is healthy. Keep daily collection running to tighten uncertainty."]
