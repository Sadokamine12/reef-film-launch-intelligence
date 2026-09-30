"""Sales and marketing decision intelligence for the Resolution launch.

The module deliberately separates prediction from evidence. Sales outlooks can use the
historical demand model plus live Resolution observations. Geography/channel rankings may
use observed campaign signals, but attributed tickets are not treated as causal lift.
Where evidence is missing, outputs remain planning estimates and say so explicitly.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from math import ceil, exp

from sqlalchemy import select
from sqlalchemy.orm import Session

from reef.campaigns.service import metrics_for
from reef.forecasting.engine import curve_target
from reef.models import Campaign, Geography
from reef.schemas import Rules

AUDIENCE_HYPOTHESES = [
    {
        "segment": "Students and young adults",
        "age": "18–29",
        "message": "An immersive music night with friends",
    },
    {
        "segment": "Couples and groups of friends",
        "age": "25–44",
        "message": "An unusual evening experience near Munich",
    },
    {
        "segment": "Music and visual-art enthusiasts",
        "age": "30–60",
        "message": "Music and immersive visual art inside a dome",
    },
    {
        "segment": "Families with teenagers",
        "age": "14–17 with adults",
        "message": "A shared fulldome experience",
    },
]


def _as_date(value: str | date | None) -> date | None:
    if value is None:
        return None
    return value if isinstance(value, date) else date.fromisoformat(value[:10])


def _booking_fraction(days_before: int, rules: Rules) -> float:
    show_target = max(1.0, curve_target(0, rules))
    return max(0.0, min(1.0, curve_target(max(0, days_before), rules) / show_target))


def _modelled_cumulative(final_tickets: int, days_before: int, rules: Rules) -> int:
    return min(final_tickets, max(0, round(final_tickets * _booking_fraction(days_before, rules))))


def _project_from_live(row: dict, final_tickets: int, horizon_days: int) -> int:
    sold = int(row.get("tickets_sold") or 0)
    days = max(0, int(row.get("days_until") or 0))
    if days <= 0:
        return max(sold, final_tickets)
    horizon = min(max(0, horizon_days), days)
    required_pace = max(0.0, (final_tickets - sold) / max(days, 1))
    v3 = row.get("velocity_3")
    v7 = row.get("velocity_7")
    observed = None
    if v3 is not None and v7 is not None:
        observed = max(0.0, 0.65 * float(v3) + 0.35 * float(v7))
    elif v3 is not None:
        observed = max(0.0, float(v3))
    elif v7 is not None:
        observed = max(0.0, float(v7))
    pace = required_pace if observed is None else 0.6 * observed + 0.4 * required_pace
    return min(final_tickets, max(sold, round(sold + pace * horizon)))


def _project_cumulative(row: dict, final_tickets: int, horizon_days: int, rules: Rules, as_of: date) -> int:
    days = max(0, int(row.get("days_until") or 0))
    if horizon_days >= days:
        return max(int(row.get("tickets_sold") or 0), final_tickets)
    if row.get("tickets_sold") is not None:
        return _project_from_live(row, final_tickets, horizon_days)

    sales_open = bool(row.get("sales_open_confirmed"))
    open_date = _as_date(row.get("sales_open_date"))
    if not sales_open or open_date is None:
        return 0
    horizon_date = as_of + timedelta(days=max(0, horizon_days))
    if horizon_date < open_date:
        return 0
    effective_horizon = max(0, (horizon_date - max(as_of, open_date)).days)
    future_days = max(0, days - effective_horizon)
    return _modelled_cumulative(final_tickets, future_days, rules)


def _current_reference(row: dict, final_tickets: int, rules: Rules, as_of: date) -> int:
    if row.get("tickets_sold") is not None:
        return int(row["tickets_sold"])
    sales_open = bool(row.get("sales_open_confirmed"))
    open_date = _as_date(row.get("sales_open_date"))
    if not sales_open or open_date is None or as_of < open_date:
        return 0
    return _modelled_cumulative(final_tickets, max(0, int(row.get("days_until") or 0)), rules)


def build_sales_intelligence(screenings: list[dict], rules: Rules, as_of: date) -> dict:
    """Build final and near-term ticket outlooks without claiming unobserved sales as facts."""
    rows: list[dict] = []
    target_pct = rules.attendance_target_pct
    for row in screenings:
        forecast = row.get("forecast") or {}
        base = forecast.get("base")
        low = forecast.get("low")
        high = forecast.get("high")
        if base is None:
            continue
        capacity = int(row["capacity"])
        target_tickets = min(capacity, ceil(capacity * target_pct / 100.0))
        current = _current_reference(row, int(base), rules, as_of)
        in_7 = _project_cumulative(row, int(base), 7, rules, as_of)
        in_14 = _project_cumulative(row, int(base), 14, rules, as_of)
        new_7 = max(0, in_7 - current)
        new_14 = max(0, in_14 - current)
        occupancy = round(int(base) / capacity * 100, 1) if capacity else 0.0
        shortfall = max(0, target_tickets - int(base))
        days = max(0, int(row.get("days_until") or 0))
        urgency = max(0.0, min(1.0, 1.0 - days / max(1, rules.paid_window_days)))
        shortfall_pressure = shortfall / max(1, capacity)
        priority_score = round(min(100.0, 70 * shortfall_pressure + 30 * urgency))
        if not row.get("sales_open_confirmed"):
            priority_score = round(priority_score * 0.4)
        risk = "HIGH" if occupancy < target_pct * 0.75 else "MEDIUM" if occupancy < target_pct else "LOW"
        v3, v7 = row.get("velocity_3"), row.get("velocity_7")
        if v3 is not None and v7 is not None:
            pace_trend = "ACCELERATING" if v3 > v7 * 1.15 else "SLOWING" if v3 < v7 * 0.85 else "STEADY"
        else:
            pace_trend = "INSUFFICIENT DATA"
        classification = "MODEL ESTIMATE" if row.get("tickets_sold") is None else "MODEL ESTIMATE"
        if not row.get("sales_open_confirmed"):
            action = "Pre-sales forecast only. Confirm ticket opening and tracking before paid promotion."
        elif row.get("stale"):
            action = "Refresh the ticket count before changing paid spend."
        elif risk == "HIGH" and days <= rules.paid_window_days:
            action = "High forecast shortfall: prioritize a controlled marketing test and review after new sales data."
        elif risk == "MEDIUM" and days <= rules.paid_window_days:
            action = "Watch booking pace and use a small evidence-gathering test if the shortfall persists."
        elif risk == "LOW":
            action = "Forecast is at or above the selected attendance target; protect budget."
        else:
            action = "Keep organic/partner activity running and reassess closer to the paid window."

        trajectory_days = sorted(
            {max(0, days), max(0, days - 7), max(0, days - 14), 0}, reverse=True
        )
        trajectory = []
        for future_days_before in trajectory_days:
            horizon = max(0, days - future_days_before)
            trajectory.append(
                {
                    "days": future_days_before,
                    "low": _project_cumulative(row, int(low if low is not None else base), horizon, rules, as_of),
                    "base": _project_cumulative(row, int(base), horizon, rules, as_of),
                    "high": _project_cumulative(row, int(high if high is not None else base), horizon, rules, as_of),
                }
            )
        rows.append(
            {
                "screening_id": row["id"],
                "date": row["date"],
                "capacity": capacity,
                "observed_tickets": row.get("tickets_sold"),
                "current_reference_tickets": current,
                "expected_new_tickets_7d": new_7,
                "expected_new_tickets_14d": new_14,
                "expected_cumulative_7d": in_7,
                "expected_cumulative_14d": in_14,
                "final_low": low,
                "final_base": base,
                "final_high": high,
                "final_occupancy_pct": occupancy,
                "target_tickets": target_tickets,
                "forecast_shortfall": shortfall,
                "risk": risk,
                "priority_score": priority_score,
                "pace_trend": pace_trend,
                "classification": classification,
                "confidence": forecast.get("confidence", "LOW"),
                "action": action,
                "trajectory": trajectory,
            }
        )

    priority = max(rows, key=lambda item: (item["priority_score"], -date.fromisoformat(item["date"]).toordinal()), default=None)
    portfolio = {
        "capacity": sum(r["capacity"] for r in rows),
        "final_low": sum(int(r["final_low"] or 0) for r in rows),
        "final_base": sum(int(r["final_base"] or 0) for r in rows),
        "final_high": sum(int(r["final_high"] or 0) for r in rows),
        "expected_new_tickets_7d": sum(r["expected_new_tickets_7d"] for r in rows),
        "expected_new_tickets_14d": sum(r["expected_new_tickets_14d"] for r in rows),
        "screenings_below_target": sum(1 for r in rows if r["risk"] != "LOW"),
        "priority_screening_id": priority["screening_id"] if priority else None,
    }
    portfolio["final_occupancy_pct"] = (
        round(portfolio["final_base"] / portfolio["capacity"] * 100, 1)
        if portfolio["capacity"]
        else 0.0
    )
    return {
        "classification": "MODEL ESTIMATE",
        "portfolio": portfolio,
        "screenings": rows,
        "evidence": {
            "final_demand": "Historical ridge baseline blended with Resolution observations when available.",
            "near_term": "Observed 3/7-day pace is blended with the pace required to reach the final estimate; without observations the management booking-curve shape is used only as a planning trajectory.",
            "warning": "Near-term cumulative values without observed Resolution sales are modelled expectations, not recorded ticket sales.",
        },
    }


def _combined_metrics(db: Session, campaigns: list[Campaign]) -> dict:
    values = [metrics_for(db, campaign.id) for campaign in campaigns]
    spend = sum(v["spend_cents"] for v in values)
    impressions = sum(v["impressions"] for v in values)
    clicks = sum(v["clicks"] for v in values)
    observed_ticket_values = [v["attributed_tickets"] for v in values if v["attributed_tickets"] is not None]
    tickets = sum(observed_ticket_values) if observed_ticket_values else None
    lpv_values = [v["landing_page_views"] for v in values if v["landing_page_views"] is not None]
    lpv = sum(lpv_values) if lpv_values else None
    imported = [v["last_imported_at"] for v in values if v.get("last_imported_at")]
    observations = sum(v["observations"] for v in values)
    return {
        "spend_cents": spend,
        "impressions": impressions,
        "clicks": clicks,
        "landing_page_views": lpv,
        "attributed_tickets": tickets,
        "ctr": round(clicks / impressions * 100, 2) if impressions else None,
        "landing_page_response": round(lpv / clicks * 100, 2) if lpv is not None and clicks else None,
        "cost_per_ticket_cents": round(spend / tickets) if tickets else None,
        "observations": observations,
        "source_label": "OBSERVED" if observations else "PLANNING ASSUMPTION",
        "last_imported_at": max(imported, default=None),
    }


def _normalise_allocations(total: int, weighted: list[tuple[str, float]]) -> dict[str, int]:
    if total <= 0 or not weighted:
        return {key: 0 for key, _ in weighted}
    denominator = sum(max(0.0, weight) for _, weight in weighted)
    if denominator <= 0:
        denominator = float(len(weighted))
        weighted = [(key, 1.0) for key, _ in weighted]
    allocations = {key: round(total * max(0.0, weight) / denominator) for key, weight in weighted}
    difference = total - sum(allocations.values())
    if allocations:
        best = max(weighted, key=lambda item: item[1])[0]
        allocations[best] += difference
    return allocations


def build_marketing_plan(
    db: Session,
    project_id: str,
    dashboard: dict,
    scenario: dict,
    rules: Rules,
) -> dict:
    """Rank screenings, geographies and channels for the selected scenario budget.

    Geography ranking is dynamic: observed campaign ticket/engagement signals can change the
    order. Distance is used only as a travel-friction prior when evidence is sparse.
    """
    budget_cents = int(scenario.get("advertising_budget_cents") or 0)
    geographies = list(
        db.scalars(select(Geography).where(Geography.project_id == project_id).order_by(Geography.min_km))
    )
    campaigns = list(db.scalars(select(Campaign).where(Campaign.project_id == project_id)))
    by_geo: dict[str, list[Campaign]] = defaultdict(list)
    by_platform: dict[str, list[Campaign]] = defaultdict(list)
    by_audience: dict[str, list[Campaign]] = defaultdict(list)
    for campaign in campaigns:
        by_geo[campaign.geography_id].append(campaign)
        by_platform[campaign.platform].append(campaign)
        if campaign.audience.strip():
            by_audience[campaign.audience.strip()].append(campaign)

    geo_rows = []
    for geography in geographies:
        perf = _combined_metrics(db, by_geo[geography.id])
        midpoint = max(0.0, (geography.min_km + geography.max_km) / 2.0)
        distance_score = exp(-midpoint / 35.0)
        cpa = perf["cost_per_ticket_cents"]
        if cpa is not None:
            reference_cpa = float(rules.ad_incremental_cpa_cents or 2500)
            response_score = 1.0 / (1.0 + cpa / max(reference_cpa, 1.0))
            score = 100 * (0.20 * distance_score + 0.80 * response_score)
            classification = "MODEL ESTIMATE"
            confidence = "MEDIUM" if perf["attributed_tickets"] and perf["attributed_tickets"] >= 5 else "LOW"
            basis = [
                "Observed attributed ticket signal adjusts the travel-friction prior.",
                "Attributed tickets are not proof of incremental lift.",
            ]
        elif perf["observations"] and perf["ctr"] is not None:
            engagement_score = min(1.0, perf["ctr"] / 2.0)
            score = 100 * (0.65 * distance_score + 0.35 * engagement_score)
            classification = "MODEL ESTIMATE"
            confidence = "LOW"
            basis = [
                "Observed click-through engagement adjusts the travel-friction prior.",
                "Clicks do not establish ticket conversion.",
            ]
        else:
            score = 100 * distance_score
            classification = "PLANNING ASSUMPTION"
            confidence = "LOW"
            basis = [
                "No campaign conversion evidence is available for this geography.",
                "Ranking currently uses venue distance as a travel-friction planning prior.",
            ]
        geo_rows.append(
            {
                "id": geography.id,
                "name": geography.name,
                "min_km": geography.min_km,
                "max_km": geography.max_km,
                "score": round(score, 1),
                "classification": classification,
                "confidence": confidence,
                "performance": perf,
                "basis": basis,
            }
        )
    geo_rows.sort(key=lambda item: (-item["score"], item["min_km"]))
    geo_allocations = _normalise_allocations(
        budget_cents, [(row["id"], max(0.01, row["score"] / 100.0) ** 2) for row in geo_rows]
    )
    total_ad_increment = sum(int(row.get("ad_increment_base") or 0) for row in scenario.get("screenings", []))
    geo_increment_alloc = _normalise_allocations(
        total_ad_increment, [(row["id"], geo_allocations.get(row["id"], 0)) for row in geo_rows]
    )
    for index, row in enumerate(geo_rows, start=1):
        row["rank"] = index
        row["recommended_share_pct"] = (
            round(geo_allocations[row["id"]] / budget_cents * 100, 1) if budget_cents else 0.0
        )
        row["recommended_budget_cents"] = geo_allocations[row["id"]]
        row["expected_incremental_tickets"] = (
            geo_increment_alloc[row["id"]]
            if scenario.get("evidence", {}).get("advertising_response", {}).get("classification") != "UNKNOWN"
            else None
        )

    sales_intelligence = dashboard.get("sales_intelligence") or {}
    sales_rows = {row["screening_id"]: row for row in sales_intelligence.get("screenings", [])}
    scenario_rows = scenario.get("screenings", [])
    screen_weights = []
    scenario_screen_meta: dict[str, dict] = {}
    target_pct = float(scenario.get("attendance_target_pct") or rules.attendance_target_pct)
    for row in scenario_rows:
        sales = sales_rows.get(row["id"], {})
        target_tickets = min(int(row["capacity"]), ceil(int(row["capacity"]) * target_pct / 100.0))
        predicted = int(row.get("predicted_base") or 0)
        shortfall = max(0, target_tickets - predicted)
        occupancy = predicted / max(1, int(row["capacity"])) * 100.0
        risk = "HIGH" if occupancy < target_pct * 0.75 else "MEDIUM" if occupancy < target_pct else "LOW"
        base_priority = float(sales.get("priority_score") or 0)
        scenario_pressure = shortfall / max(1, int(row["capacity"])) * 70.0
        priority_score = round(min(100.0, max(base_priority, scenario_pressure)))
        urgency = max(1.0, priority_score / 20.0)
        screen_weights.append((row["id"], max(0.1, shortfall * urgency)))
        scenario_screen_meta[row["id"]] = {
            "target_tickets": target_tickets,
            "shortfall": shortfall,
            "risk": risk,
            "priority_score": priority_score,
        }
    screening_allocations = _normalise_allocations(budget_cents, screen_weights)
    screening_increment_alloc = _normalise_allocations(total_ad_increment, screen_weights)
    screening_plan = []
    for row in scenario_rows:
        meta = scenario_screen_meta[row["id"]]
        screening_plan.append(
            {
                "screening_id": row["id"],
                "date": row["date"],
                "priority_score": meta["priority_score"],
                "risk": meta["risk"],
                "forecast_shortfall": meta["shortfall"],
                "target_tickets": meta["target_tickets"],
                "predicted_tickets": row.get("predicted_base"),
                "recommended_budget_cents": screening_allocations.get(row["id"], 0),
                "expected_incremental_tickets": (
                    screening_increment_alloc.get(row["id"], 0)
                    if scenario.get("evidence", {}).get("advertising_response", {}).get("classification") != "UNKNOWN"
                    else None
                ),
            }
        )
    screening_plan.sort(key=lambda item: (-item["priority_score"], item["date"]))

    channel_rows = []
    initial_total = max(1, rules.meta_test_cents + rules.google_test_cents)
    fallback_shares = {
        "META": rules.meta_test_cents / initial_total,
        "GOOGLE": rules.google_test_cents / initial_total,
    }
    channel_weights = []
    for platform in ["META", "GOOGLE"]:
        perf = _combined_metrics(db, by_platform[platform])
        cpa = perf["cost_per_ticket_cents"]
        if cpa is not None:
            weight = 1.0 / max(1.0, cpa)
            classification = "MODEL ESTIMATE"
            basis = "Observed attributed-ticket CPA; attribution is not causal lift."
        elif perf["observations"] and perf["ctr"] is not None:
            weight = max(0.01, perf["ctr"] / 100.0)
            classification = "MODEL ESTIMATE"
            basis = "Observed CTR signal only; ticket conversion is unknown."
        else:
            weight = fallback_shares[platform]
            classification = "PLANNING ASSUMPTION"
            basis = "No response evidence yet; uses the configured controlled-test split."
        channel_weights.append((platform, weight))
        channel_rows.append(
            {
                "platform": platform,
                "classification": classification,
                "performance": perf,
                "basis": basis,
            }
        )
    channel_allocations = _normalise_allocations(budget_cents, channel_weights)
    for row in channel_rows:
        row["recommended_budget_cents"] = channel_allocations[row["platform"]]
        row["recommended_share_pct"] = (
            round(channel_allocations[row["platform"]] / budget_cents * 100, 1) if budget_cents else 0.0
        )

    audience_rows = []
    observed_audiences = []
    for audience, audience_campaigns in by_audience.items():
        perf = _combined_metrics(db, audience_campaigns)
        if perf["observations"]:
            observed_audiences.append(
                {
                    "segment": audience,
                    "classification": "MODEL ESTIMATE",
                    "performance": perf,
                    "basis": "Observed campaign performance for this audience label; attributed tickets are not causal lift.",
                }
            )
    if observed_audiences:
        observed_audiences.sort(
            key=lambda item: (
                item["performance"]["cost_per_ticket_cents"] is None,
                item["performance"]["cost_per_ticket_cents"] or 10**12,
                -(item["performance"]["attributed_tickets"] or 0),
            )
        )
        audience_rows = observed_audiences
    else:
        audience_rows = [
            {**item, "classification": "PLANNING ASSUMPTION", "performance": None, "basis": "Audience hypothesis to test; no REEF response data yet."}
            for item in AUDIENCE_HYPOTHESES
        ]

    top_geo = geo_rows[0] if geo_rows else None
    top_screening = screening_plan[0] if screening_plan else None
    top_channel = max(channel_rows, key=lambda item: item["recommended_budget_cents"], default=None)
    if budget_cents <= 0:
        recommendation = "No paid budget selected. Use the ranking to decide where the first evidence-gathering test should run."
    elif top_screening and top_geo:
        recommendation = (
            f"Prioritize {top_screening['date']} and test {top_geo['name']} first. "
            "Re-rank after importing new sales and campaign results."
        )
    else:
        recommendation = "Collect ticket and campaign evidence before scaling paid promotion."

    warnings = [
        "Geography score is a decision ranking, not a probability that a resident will buy a ticket.",
        "Distance is used as a travel-friction planning prior until stronger location conversion evidence exists.",
    ]
    if total_ad_increment <= 0 and budget_cents > 0:
        warnings.append(
            "Expected incremental tickets by place remain unavailable because advertising lift has not been estimated; enter a planning CPA or collect campaign attribution evidence."
        )
    return {
        "classification": "MODEL ESTIMATE" if any(row["performance"]["observations"] for row in geo_rows) else "PLANNING ASSUMPTION",
        "advertising_budget_cents": budget_cents,
        "recommendation": recommendation,
        "target_screening": top_screening,
        "top_geography": top_geo,
        "top_channel": top_channel,
        "screenings": screening_plan,
        "geographies": geo_rows,
        "channels": channel_rows,
        "audiences": audience_rows,
        "warnings": warnings,
    }
