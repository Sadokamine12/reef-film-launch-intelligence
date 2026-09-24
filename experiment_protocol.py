from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import pandas as pd

from market_context import get_market
from project_config import load_config


def build_experiment_plan(market: dict | None = None) -> pd.DataFrame:
    """Build the complete EUR 240 learning plan for the selected target market."""
    market = market or get_market()
    zones = [str(z["area"]) for z in market.get("zones", [])][:3]
    if len(zones) < 3:
        zones = (zones + [market.get("label", "Selected city")] * 3)[:3]
    city = str(market.get("label", "Selected city"))
    search_area = str(market.get("search_area", city))
    rows = [{
        "step": "W0", "wave": "Baseline", "dependency": "Tickets live", "channel": "No paid media",
        "city": city, "area": "All", "age_band": "20-60", "creative": "None", "planned_spend_eur": 0,
        "duration_days": 2, "purpose": "Measure pre-campaign Resolution sales velocity", "control_group": "yes",
    }]
    for area in zones:
        for creative in ["SXSW proof", "Music + 360 experience"]:
            rows.append({
                "step": f"W1-{len(rows):02d}", "wave": "Geo + creative", "dependency": "After baseline window",
                "channel": "Meta", "city": city, "area": area, "age_band": "20-60", "creative": creative,
                "planned_spend_eur": 15, "duration_days": 3, "purpose": "Learn geography and creative engagement",
                "control_group": "no",
            })
    for area in ["WINNER_GEO_1", "WINNER_GEO_2"]:
        for age in ["20-34", "35-60"]:
            rows.append({
                "step": f"W2-{len(rows):02d}", "wave": "Age refinement",
                "dependency": "Use top 2 W1 geos + winning creative", "channel": "Meta", "city": city,
                "area": area, "age_band": age, "creative": "WINNER_CREATIVE", "planned_spend_eur": 20,
                "duration_days": 3, "purpose": "Learn age response without fragmenting Wave 1", "control_group": "no",
            })
    rows.append({
        "step": "W3-SEARCH", "wave": "Intent", "dependency": "Ticket landing page live", "channel": "Google Search",
        "city": city, "area": search_area, "age_band": "20-60", "creative": "High-intent text",
        "planned_spend_eur": 40, "duration_days": 4, "purpose": "Compare high-intent search against Meta",
        "control_group": "no",
    })
    rows.append({
        "step": "W3-RET", "wave": "Retargeting", "dependency": "Only if retargeting pool is large enough",
        "channel": "Retargeting", "city": city, "area": "Prior site/video visitors", "age_band": "20-60",
        "creative": "Scarcity / next Tuesday", "planned_spend_eur": 30, "duration_days": 4,
        "purpose": "Measure warm-audience efficiency", "control_group": "no",
    })
    return pd.DataFrame(rows)


def campaign_timeline() -> pd.DataFrame:
    cfg = load_config()
    first_show = pd.to_datetime(cfg["screenings"]["dates"][0]).date()
    rows = [
        ("P0", first_show - timedelta(days=120), first_show - timedelta(days=31), "Pre-launch learning", 0, "Collect comparable ESO sales daily/regularly; prepare creatives, UTMs and booking-page discovery.", "ESO snapshots"),
        ("P1", first_show - timedelta(days=30), first_show - timedelta(days=29), "Resolution no-paid baseline", 0, "Once tickets are live, keep paid media off for ~48h and record Resolution seat movement.", "Daily seat delta"),
        ("P2", first_show - timedelta(days=28), first_show - timedelta(days=25), "Wave 1 — geo + creative", 90, "Selected city: 3 geos × 2 creatives; broad 20–60 target; keep ad sets separate.", "CTR, LPV, verified tickets if available"),
        ("P3", first_show - timedelta(days=24), first_show - timedelta(days=21), "Wave 2 — age refinement", 80, "Top 2 Wave-1 geos × 2 age bands using the winning creative.", "CTR, LPV, ticket CPA"),
        ("P4", first_show - timedelta(days=20), first_show - timedelta(days=17), "Search + retarget validation", 70, "€40 Search + €30 retargeting only if audience pool is large enough.", "Intent CPA / conversion"),
        ("P5", first_show - timedelta(days=16), first_show + timedelta(days=21), "Scale reserve across 4 Tuesdays", 260, "Move budget only to cells with measured evidence; reallocate after every Tuesday.", "Incremental ticket lift / CPA"),
    ]
    return pd.DataFrame(rows, columns=["phase", "start_date", "end_date", "name", "budget_eur", "action", "primary_measure"])


def attribution_requirements() -> pd.DataFrame:
    return pd.DataFrame([
        {"level":"A", "method":"ESO purchase source report", "what_it_enables":"Tracked sales by source; incrementality still needs a control", "required_for":"Cell-level purchase tracking"},
        {"level":"B", "method":"Unique promo/source code", "what_it_enables":"Tracked sales by code; incrementality still needs a control", "required_for":"Cell-level purchase tracking"},
        {"level":"C", "method":"Reliable platform sale event", "what_it_enables":"Tracked sales from instrumented campaigns", "required_for":"Purchase tracking"},
        {"level":"D", "method":"Controlled holdout or staggered test", "what_it_enables":"Incremental ticket estimate with uncertainty", "required_for":"Ticket-lift ML"},
        {"level":"E", "method":"Aggregate seat inventory only", "what_it_enables":"Uncertain overall campaign comparison only", "required_for":"Baseline monitoring"},
    ])


def write_protocol_files() -> None:
    Path("data").mkdir(exist_ok=True)
    campaign_timeline().to_csv("data/campaign_timeline.csv", index=False)
    attribution_requirements().to_csv("data/attribution_requirements.csv", index=False)
    build_experiment_plan().to_csv("data/experiment_plan.csv", index=False)
