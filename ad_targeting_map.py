from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple
import math

import pandas as pd

from market_context import get_market

# U6 nodes are used only when the selected market uses the U6 corridor.
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
    if "test_weight" not in out:
        out["test_weight"] = 1.0
    total = pd.to_numeric(out["test_weight"], errors="coerce").fillna(0).sum()
    out["test_weight"] = (1 / max(1, len(out))) if total <= 0 else out["test_weight"] / total
    return out


def planned_zones(
    total_budget: float = 500,
    validation_budget: float = 240,
    search_budget: float = 40,
    market: dict | None = None,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Return the selected city's balanced first-wave zones.

    Geography is a test choice, not a learned success probability. The first wave
    always spends EUR 90 across three zones (EUR 30/zone, split across two
    creatives in the experiment page).
    """
    market = market or get_market()
    total_budget = max(0.0, float(total_budget))
    validation_budget = min(max(0.0, float(validation_budget)), total_budget)
    search_budget = min(max(0.0, float(search_budget)), validation_budget)
    geo_budget = min(90.0, validation_budget)
    later_tests = max(0.0, validation_budget - search_budget - geo_budget)
    scale_reserve = max(0.0, total_budget - validation_budget)

    zones = pd.DataFrame(market.get("zones", [])).copy()
    if zones.empty:
        zones = pd.DataFrame([{
            "area": market.get("label", "Selected city"),
            "lat": market.get("center", {}).get("lat", 48.1372),
            "lon": market.get("center", {}).get("lon", 11.5756),
            "radius_km": 2.5,
            "role": "Test zone",
            "age": "20–60",
            "why": "Selected market",
            "creative": "Two creative variants",
        }])
    zones = zones.head(3).copy()
    zones["priority_score"] = 100
    zones["test_weight"] = 1 / max(1, len(zones))
    zones = _normalise_weights(zones)
    per_zone = geo_budget / max(1, len(zones))
    zones["budget_eur"] = per_zone
    zones["radius_m"] = (pd.to_numeric(zones["radius_km"], errors="coerce").fillna(2.5) * 1000).astype(int)
    zones["label"] = zones.apply(lambda r: f"{r['area']}\nEUR {int(round(r['budget_eur']))}", axis=1)
    zones["market_city"] = market.get("label", "Selected city")

    meta = {
        "market_city": market.get("label", "Selected city"),
        "search_area": market.get("search_area", market.get("label", "Selected city")),
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
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def measured_area_performance(history: pd.DataFrame, market_city: str | None = None) -> pd.DataFrame:
    """Summarise verified tracked purchases; this is not incremental lift."""
    if history is None or history.empty:
        return pd.DataFrame()
    required = {"area", "spend_eur", "tickets_attributed"}
    if not required.issubset(history.columns):
        return pd.DataFrame()
    df = history.copy()
    if market_city and "city" in df.columns:
        city = df["city"].fillna("").astype(str).str.strip()
        if city.ne("").any():
            df = df[city.str.casefold().eq(str(market_city).strip().casefold())]
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
        agg["measured_score"] = 100 if hi <= lo else 100 - ((agg["ticket_cpa"].clip(upper=hi) - lo) / (hi - lo) * 45)
    else:
        agg["measured_score"] = 50
    max_t = max(1.0, float(agg["tickets"].max()))
    agg["measured_score"] = (0.75 * agg["measured_score"] + 0.25 * (agg["tickets"] / max_t * 100)).round(0)
    return agg.sort_values(["measured_score", "tickets"], ascending=False)


def join_measured_to_zones(zones: pd.DataFrame, measured: pd.DataFrame) -> pd.DataFrame:
    out = zones.copy()
    if measured is None or measured.empty:
        out["display_score"] = out["priority_score"]
        out["score_basis"] = "Balanced test priority"
        return out

    norm = lambda s: str(s).strip().casefold()
    measured = measured.copy()
    measured["_k"] = measured["area"].map(norm)
    out["_k"] = out["area"].map(norm)
    out = out.merge(
        measured[["_k", "spend_eur", "tickets", "ticket_cpa", "observations", "measured_score"]],
        on="_k", how="left",
    )
    out["display_score"] = out["measured_score"].fillna(out["priority_score"])
    out["score_basis"] = out["measured_score"].apply(
        lambda v: "Measured tracked-purchase CPA" if pd.notna(v) else "Balanced pre-campaign test"
    )
    return out.drop(columns=["_k"], errors="ignore")


def u6_path_frame() -> pd.DataFrame:
    return pd.DataFrame(U6_PATH)
