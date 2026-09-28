from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import pandas as pd

from market_context import get_market
from project_config import load_config


def build_experiment_plan(market: dict | None = None) -> pd.DataFrame:
    """Build the controlled EUR 100 first paid test for the selected market."""
    market = market or get_market()
    zones = [str(z["area"]) for z in market.get("zones", [])][:2]
    if len(zones) < 2:
        zones = (zones + [market.get("label", "Selected city")] * 2)[:2]
    city = str(market.get("label", "Selected city"))
    search_area = str(market.get("search_area", city))

    rows = [{
        "step": "W0",
        "wave": "Baseline",
        "dependency": "Tickets live",
        "channel": "No paid media",
        "city": city,
        "area": "All",
        "age_band": "20-60",
        "creative": "None",
        "planned_spend_eur": 0.0,
        "duration_days": 2,
        "purpose": "Measure no-paid Resolution sales velocity",
        "control_group": "yes",
    }]

    # EUR 70 Meta: two local zones x two controlled creative angles.
    for area in zones:
        for creative in ["Experience", "Event"]:
            rows.append({
                "step": f"W1-{len(rows):02d}",
                "wave": "Geo + creative",
                "dependency": "After organic baseline",
                "channel": "Meta",
                "city": city,
                "area": area,
                "age_band": "20-60",
                "creative": creative,
                "planned_spend_eur": 17.5,
                "duration_days": 7,
                "purpose": "Compare local geography and creative response",
                "control_group": "no",
            })

    # EUR 30 Google Search: capture high-intent local demand in the same test window.
    rows.append({
        "step": "W1-SEARCH",
        "wave": "Intent",
        "dependency": "Ticket landing page live",
        "channel": "Google Search",
        "city": city,
        "area": search_area,
        "age_band": "20-60",
        "creative": "Event / high-intent text",
        "planned_spend_eur": 30.0,
        "duration_days": 7,
        "purpose": "Measure high-intent search response",
        "control_group": "no",
    })

    return pd.DataFrame(rows)


def campaign_timeline() -> pd.DataFrame:
    """Business-first calendar matching the management command center."""
    cfg = load_config()
    launch = cfg.get("launch_plan", {})
    first_show = pd.to_datetime(cfg["screenings"]["dates"][0]).date()
    sales_open = pd.to_datetime(launch.get("sales_open_target", "2026-11-16")).date()
    paid_start = pd.to_datetime(launch.get("paid_test_start", "2027-01-04")).date()
    paid_end = pd.to_datetime(launch.get("paid_test_end", "2027-01-10")).date()

    rows = [
        (
            "P0",
            date.today(),
            sales_open,
            "Launch readiness",
            0,
            "Confirm booking links, UTMs, event listings and the two approved creative angles.",
            "Readiness",
        ),
        (
            "P1",
            sales_open,
            paid_start - timedelta(days=1),
            "Organic booking baseline",
            0,
            "Keep paid media off and learn the natural Resolution booking pace.",
            "Tickets/day by screening",
        ),
        (
            "P2",
            paid_start,
            paid_end,
            "Controlled paid test",
            100,
            "Run EUR 70 Meta + EUR 30 Google; compare response without committing the remaining budget.",
            "Sales pace, CTR, LPV, verified purchases if available",
        ),
        (
            "P3",
            paid_end + timedelta(days=1),
            first_show - timedelta(days=2),
            "Conditional scaling",
            0,
            "Release budget only for screenings below the healthy curve and only into evidence-supported channels/areas.",
            "Gap to target / marginal CPA",
        ),
        (
            "P4",
            first_show - timedelta(days=1),
            pd.to_datetime(cfg["screenings"]["dates"][-1]).date(),
            "Show-specific recovery",
            0,
            "Use EUR 8-25/day only on the Tuesday that needs help; stop promotion when a show is near full.",
            "Per-screening pace",
        ),
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
