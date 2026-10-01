from datetime import datetime, timezone

from reef.campaigns.service import metrics_for
from reef.models import Campaign
from sqlalchemy import select
from sqlalchemy.orm import Session

REPORTS = {
    "daily": "Daily ticket report",
    "campaigns": "Campaign performance report",
    "screenings": "Screening performance report",
    "budget": "Budget report",
    "post-event": "Post-event report",
    "learnings": "Marketing learnings",
}


def report(db: Session, kind: str, dashboard: dict) -> dict:
    project_id = dashboard["project"]["id"]
    screenings = dashboard["screenings"]
    rows, notes = [], []
    if kind in {"daily", "screenings", "post-event"}:
        rows = [
            {
                "screening": s["date"],
                "observed_tickets": s["tickets_sold"],
                "capacity": s["capacity"],
                "target": s["decision"]["target_today"],
                "status": s["decision"]["status"],
                "velocity_3": s["velocity_3"],
                "velocity_7": s["velocity_7"],
                "forecast_low": s["forecast"]["low"],
                "forecast_base": s["forecast"]["base"],
                "forecast_high": s["forecast"]["high"],
                "source": s["source_label"],
                "observed_at": s["observed_at"],
                "recommended_eur": s["decision"]["recommended_budget_cents"] / 100,
                "forecast_risk": next((x["forecast_risk"] for x in dashboard.get("sales_intelligence", {}).get("screenings", []) if x["screening_id"] == s["id"]), None),
                "action_urgency": next((x["action_urgency"] for x in dashboard.get("sales_intelligence", {}).get("screenings", []) if x["screening_id"] == s["id"]), None),
            }
            for s in screenings
        ]
        notes.append(
            "Targets are management assumptions. Forecast ranges come from the grouped historical ridge baseline and live Resolution pace when available; they are planning ranges, not calibrated prediction intervals."
        )
        if kind == "post-event":
            notes.append(
                "Final attendance must be reconciled with ESO. Pre-event snapshots are not final outcomes."
            )
    elif kind == "budget":
        rows = [
            {
                "channel": name,
                "ceiling_eur": c["ceiling_cents"] / 100,
                "spent_eur": c["spent_cents"] / 100,
                "committed_eur": c["committed_cents"] / 100,
                "available_eur": c["available_cents"] / 100,
            }
            for name, c in dashboard["budget"]["channels"].items()
        ]
        rows.append(
            {
                "channel": "PROTECTED RESERVE",
                "ceiling_eur": dashboard["budget"]["reserve_cents"] / 100,
                "spent_eur": 0,
                "committed_eur": 0,
                "available_eur": 0,
            }
        )
        notes.append(
            "The ceiling is a maximum, not a spending commitment. Actual over-spend is retained and flagged."
        )
    else:
        for c in db.scalars(select(Campaign).where(Campaign.project_id == project_id)):
            m = metrics_for(db, c.id)
            rows.append(
                {
                    "campaign": c.name,
                    "platform": c.platform,
                    "screening": c.screening_id,
                    "zone": c.geography_id,
                    "creative": c.creative_id,
                    "spend_eur": m["spend_cents"] / 100,
                    "impressions": m["impressions"],
                    "clicks": m["clicks"],
                    "ctr_pct": m["ctr"],
                    "landing_page_views": m["landing_page_views"],
                    "attributed_tickets": m["attributed_tickets"],
                    "cost_per_ticket_eur": m["cost_per_ticket_cents"] / 100
                    if m["cost_per_ticket_cents"] is not None
                    else None,
                    "source": m["source_label"],
                }
            )
        notes.append(
            "Platform-attributed tickets are not proven incremental sales. Cross-platform attribution may overlap."
        )
        if kind == "learnings":
            evidence = [r for r in rows if (r["attributed_tickets"] or 0) >= 5]
            notes.append(
                "Compare creative and geography tests with at least five attributed tickets; treat differences as directional."
            )
            if not evidence:
                notes.append(
                    "Insufficient ticket attribution to recommend a winning creative or geography. Keep the next test local."
                )
            else:
                best = min(evidence, key=lambda r: r["cost_per_ticket_eur"])
                notes.append(
                    f"Lowest observed cost per attributed ticket: {best['campaign']}. Validate with a controlled follow-up test."
                )
    return {
        "kind": kind,
        "title": REPORTS[kind],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": dashboard["project"],
        "rows": rows,
        "notes": notes,
        "recommendation": dashboard["today"]["headline"],
    }
