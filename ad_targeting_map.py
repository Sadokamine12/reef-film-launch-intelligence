from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple
import math
import pandas as pd

# Planning pins for the Resolution @ ESO campaign.
# ESO coordinates are the venue's published GPS position.
# Other pins are planning centres for ad-radius tests, not venue addresses.
DEFAULT_ZONES = [
    {
        "area": "ESO / Forschungszentrum",
        "lat": 48.259828,
        "lon": 11.670136,
        "radius_km": 2.5,
        "priority_score": 100,
        "test_weight": 0.40,
        "age": "20–60",
        "role": "Primary",
        "why": "Venue + research campus + immediate catchment",
        "creative": "SXSW proof + immersive dome experience",
    },
    {
        "area": "Garching / Hochbrück",
        "lat": 48.247326,
        "lon": 11.631008,
        "radius_km": 2.5,
        "priority_score": 89,
        "test_weight": 0.225,
        "age": "25–60",
        "role": "Local",
        "why": "Close to ESO; local residents, workers and U6 access",
        "creative": "Four Tuesday nights + easy local access",
    },
    {
        "area": "Studentenstadt / Freimann",
        "lat": 48.183522,
        "lon": 11.607710,
        "radius_km": 2.5,
        "priority_score": 84,
        "test_weight": 0.20,
        "age": "20–39",
        "role": "U6",
        "why": "Direct U6 corridor; younger culture/experience audience",
        "creative": "Music + 360° visual experience",
    },
    {
        "area": "Universität / Schwabing",
        "lat": 48.150850,
        "lon": 11.580250,
        "radius_km": 2.5,
        "priority_score": 80,
        "test_weight": 0.175,
        "age": "20–49",
        "role": "Culture",
        "why": "University, culture and music audience on the same U6 line",
        "creative": "Award-winning immersive music event",
    },
]

# Key U6 nodes used only to explain the travel corridor visually.
U6_PATH = [
    {"name": "Universität", "lat": 48.150850, "lon": 11.580250},
    {"name": "Münchner Freiheit", "lat": 48.161345, "lon": 11.586414},
    {"name": "Studentenstadt", "lat": 48.183522, "lon": 11.607710},
    {"name": "Freimann", "lat": 48.191050, "lon": 11.615200},
    {"name": "Garching-Hochbrück", "lat": 48.247326, "lon": 11.631008},
    {"name": "Garching", "lat": 48.249050, "lon": 11.651100},
    {"name": "Garching-Forschungszentrum", "lat": 48.264679, "lon": 11.671300},
]


def _normalise_weights(zones: pd.DataFrame) -> pd.DataFrame:
    out = zones.copy()
    total = pd.to_numeric(out["test_weight"], errors="coerce").fillna(0).sum()
    if total <= 0:
        out["test_weight"] = 1 / max(1, len(out))
    else:
        out["test_weight"] = out["test_weight"] / total
    return out


def planned_zones(total_budget: float = 500, validation_budget: float = 240, search_budget: float = 40) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Show the actual first-wave geography spend from the locked experiment plan."""
    total_budget = max(0.0, float(total_budget))
    validation_budget = min(max(0.0, float(validation_budget)), total_budget)
    search_budget = min(max(0.0, float(search_budget)), validation_budget)
    geo_budget = min(max(0.0, validation_budget - search_budget), validation_budget * 90 / 240)
    later_tests = max(0.0, validation_budget - search_budget - geo_budget)
    scale_reserve = max(0.0, total_budget - validation_budget)

    zones = _normalise_weights(pd.DataFrame(DEFAULT_ZONES))
    shares = {"ESO / Forschungszentrum": 1/3, "Garching / Hochbrück": 1/3, "Universität / Schwabing": 1/3}
    zones["budget_eur"] = zones["area"].map(shares).fillna(0).mul(geo_budget).round(0).astype(int)
    # Preserve the exact geo total after rounding.
    delta = int(round(geo_budget - zones["budget_eur"].sum()))
    if delta and len(zones):
        zones.loc[zones.index[0], "budget_eur"] += delta
    zones["radius_m"] = (zones["radius_km"] * 1000).astype(int)
    zones["label"] = zones.apply(lambda r: f"{r['area']}\nEUR {int(r['budget_eur'])}", axis=1)

    meta = {
        "total_budget": total_budget,
        "validation_budget": validation_budget,
        "geo_budget": geo_budget,
        "search_budget": search_budget,
        "later_tests": later_tests,
        "scale_reserve": scale_reserve,
    }
    return zones, meta


def load_campaign_history(path: str | Path = "data/campaign_history.csv") -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    return df


def measured_area_performance(history: pd.DataFrame) -> pd.DataFrame:
    """Summarise tracked purchases; this is not an incremental-lift estimate."""
    if history is None or history.empty:
        return pd.DataFrame()
    required = {"area", "spend_eur", "tickets_attributed"}
    if not required.issubset(history.columns):
        return pd.DataFrame()
    df = history.copy()
    df["spend_eur"] = pd.to_numeric(df["spend_eur"], errors="coerce")
    df["tickets_attributed"] = pd.to_numeric(df["tickets_attributed"], errors="coerce")
    df = df.dropna(subset=["area", "spend_eur", "tickets_attributed"])
    if "label_source" in df.columns:
        verified = {"platform_conversion", "promo_code", "eso_source_report"}
        df = df[df["label_source"].fillna("").astype(str).str.lower().isin(verified)]
    df = df[(df["spend_eur"] > 0) & (df["tickets_attributed"] >= 0)]
    if df.empty:
        return pd.DataFrame()

    agg = df.groupby("area", as_index=False).agg(
        spend_eur=("spend_eur", "sum"),
        tickets=("tickets_attributed", "sum"),
        observations=("area", "size"),
    )
    agg["ticket_cpa"] = agg.apply(lambda r: r["spend_eur"] / r["tickets"] if r["tickets"] > 0 else math.inf, axis=1)
    finite = agg.loc[agg["ticket_cpa"].replace([math.inf], pd.NA).notna(), "ticket_cpa"]
    if len(finite):
        lo, hi = float(finite.min()), float(finite.max())
        if hi > lo:
            agg["measured_score"] = 100 - ((agg["ticket_cpa"].clip(upper=hi) - lo) / (hi - lo) * 45)
        else:
            agg["measured_score"] = 100
    else:
        agg["measured_score"] = 50
    # Ticket volume also matters, but less than CPA for the first tests.
    max_t = max(1.0, float(agg["tickets"].max()))
    agg["measured_score"] = (0.75 * agg["measured_score"] + 0.25 * (agg["tickets"] / max_t * 100)).round(0)
    return agg.sort_values(["measured_score", "tickets"], ascending=False)


def join_measured_to_zones(zones: pd.DataFrame, measured: pd.DataFrame) -> pd.DataFrame:
    out = zones.copy()
    if measured is None or measured.empty:
        out["display_score"] = out["priority_score"]
        out["score_basis"] = "Pre-campaign priority"
        return out

    # Match normalised area names where possible; unmatched zones remain prior-only.
    norm = lambda s: str(s).strip().lower().replace("forschungszentrum / eso", "eso").replace(" / ", " ")
    measured = measured.copy()
    measured["_k"] = measured["area"].map(norm)
    out["_k"] = out["area"].map(norm)
    out = out.merge(measured[["_k", "spend_eur", "tickets", "ticket_cpa", "observations", "measured_score"]], on="_k", how="left")
    out["display_score"] = out["measured_score"].fillna(out["priority_score"])
    out["score_basis"] = out["measured_score"].apply(lambda v: "Measured tracked-purchase CPA" if pd.notna(v) else "Pre-campaign test priority")
    return out.drop(columns=["_k"], errors="ignore")


def u6_path_frame() -> pd.DataFrame:
    return pd.DataFrame(U6_PATH)
