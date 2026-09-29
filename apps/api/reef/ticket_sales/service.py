from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from reef.campaigns.service import budget
from reef.forecasting.engine import BookingCurveForecast, ForecastInput, sales_velocity
from reef.marketing.decisions import decide
from reef.models import Campaign, Project, Screening, Snapshot
from reef.schemas import Rules
from sqlalchemy import select
from sqlalchemy.orm import Session


def dashboard(db: Session, project: Project, as_of: datetime | None = None) -> dict:
    as_of = as_of or datetime.now(timezone.utc)
    today = as_of.astimezone(ZoneInfo(project.timezone)).date()
    rules = Rules.model_validate(project.rules)
    money = budget(db, project.id, rules)
    available_meta = min(money["available_cents"], money["channels"]["META"]["available_cents"])
    screenings = list(
        db.scalars(select(Screening).where(Screening.project_id == project.id).order_by(Screening.date))
    )
    rows = []
    for screening in screenings:
        snapshots = list(
            db.scalars(
                select(Snapshot)
                .where(Snapshot.screening_id == screening.id, Snapshot.observed_at <= as_of)
                .order_by(Snapshot.observed_at)
            )
        )
        latest = snapshots[-1] if snapshots else None
        sold = latest.tickets_sold if latest else None
        stale = (
            latest is not None
            and (as_of - latest.observed_at).total_seconds() > rules.stale_after_hours * 3600
        )
        days = (screening.date - today).days
        ended = days < 0
        if screening.time:
            show_at = datetime.combine(
                screening.date, time.fromisoformat(screening.time), ZoneInfo(project.timezone)
            )
            ended = as_of >= show_at
        sales_open = (
            screening.sales_open_confirmed
            and screening.sales_open_date is not None
            and today >= screening.sales_open_date
        )
        v3, v7 = sales_velocity(snapshots, 3, as_of), sales_velocity(snapshots, 7, as_of)
        forecast = BookingCurveForecast().predict(
            ForecastInput(days, screening.capacity, sold, v3, v7, stale), rules
        )
        decision = decide(
            sold=sold,
            days=-1 if ended else days,
            stale=stale,
            as_of=today,
            booking_ready=bool(screening.booking_url),
            sales_open=sales_open,
            rules=rules,
        )
        if not sales_open:
            decision["next_review"] = str(max(today, (screening.sales_open_date or rules.sales_open_target)))
        elif not latest:
            decision["next_review"] = str(today)
        if ended:
            forecast.update(
                low=sold,
                base=sold,
                high=sold,
                confidence="OBSERVED" if sold is not None else "LOW",
                confidence_note="Last observed count; verify final attendance with ESO.",
            )
        rows.append(
            {
                "id": screening.id,
                "date": str(screening.date),
                "time": screening.time,
                "capacity": screening.capacity,
                "booking_url": screening.booking_url,
                "sales_open_date": str(screening.sales_open_date) if screening.sales_open_date else None,
                "sales_open_confirmed": screening.sales_open_confirmed,
                "days_until": days,
                "tickets_sold": sold,
                "seats_remaining": screening.capacity - sold if sold is not None else None,
                "observed_at": latest.observed_at.isoformat() if latest else None,
                "source_label": latest.source_label if latest else "PLANNING ASSUMPTION",
                "stale": stale,
                "velocity_3": v3,
                "velocity_7": v7,
                "acceleration": round(v3 - v7, 2) if v3 is not None and v7 is not None else None,
                "forecast": forecast,
                "decision": decision,
                "actual_curve": [
                    {
                        "days": (
                            screening.date - s.observed_at.astimezone(ZoneInfo(project.timezone)).date()
                        ).days,
                        "tickets": s.tickets_sold,
                        "observed_at": s.observed_at.isoformat(),
                    }
                    for s in snapshots
                ],
            }
        )
    # Allocate scarce recommendations once across the project, prioritising urgent early shows.
    for row in sorted(rows, key=lambda r: (0 if r["decision"]["status"] == "ACTION" else 1, r["date"])):
        d = row["decision"]
        active = db.scalar(
            select(Campaign.id).where(
                Campaign.screening_id == row["id"], Campaign.status.in_(["PLANNED", "ACTIVE", "PAUSED"])
            )
        )
        if active and d["recommended_budget_cents"]:
            d.update(
                recommended_budget_cents=0,
                daily_budget_cents=0,
                action="Review the existing campaign before committing additional budget.",
            )
        elif d["recommended_budget_cents"]:
            allocation = min(d["recommended_budget_cents"], available_meta)
            # Whole-cent daily rate times duration prevents displayed daily rate exceeding the cap.
            d["daily_budget_cents"] = allocation // d["duration_days"]
            d["recommended_budget_cents"] = d["daily_budget_cents"] * d["duration_days"]
            available_meta -= d["recommended_budget_cents"]
            if not d["recommended_budget_cents"]:
                d["action"] = "Use organic and partner promotion. No uncommitted Meta budget is available."
    known = [r for r in rows if r["tickets_sold"] is not None]
    actionable = sorted(
        rows,
        key=lambda r: (
            {
                "ACTION": 0,
                "WATCH": 1,
                "DATA_NEEDED": 2,
                "NEAR_FULL": 3,
                "ON_TRACK": 4,
                "PRE_LAUNCH": 5,
                "COMPLETE": 6,
            }[r["decision"]["status"]],
            r["date"],
        ),
    )
    first = actionable[0]
    if all(r["decision"]["status"] == "PRE_LAUNCH" for r in rows):
        headline = "Spend €0 today. Prepare the ticket-sales launch."
    elif first["decision"]["status"] in {"ACTION", "WATCH"}:
        headline = f"{datetime.fromisoformat(first['date']).strftime('%d %b')} is behind target by {first['forecast']['gap_to_target']} tickets."
    elif first["decision"]["status"] == "DATA_NEEDED":
        headline = "Update ticket sales. Make the next decision with evidence."
    elif first["decision"]["status"] == "NEAR_FULL":
        headline = "Stop spend on near-full shows. Move attention to the next Tuesday."
    elif first["decision"]["status"] == "COMPLETE":
        headline = "Close the campaign. Capture what worked."
    else:
        headline = "Sales are on track. Keep the budget unspent."
    return {
        "as_of": as_of.isoformat(),
        "project": {
            "id": project.id,
            "name": project.name,
            "film": project.film,
            "venue": project.venue,
            "latitude": project.latitude,
            "longitude": project.longitude,
            "timezone": project.timezone,
        },
        "summary": {
            "capacity": sum(r["capacity"] for r in rows),
            "tickets_sold": sum(r["tickets_sold"] for r in known) if len(known) == len(rows) else None,
            "known_tickets": sum(r["tickets_sold"] for r in known),
            "observed_screenings": len(known),
            "seats_remaining": sum(r["seats_remaining"] for r in known) if len(known) == len(rows) else None,
            "target_today": sum(r["decision"]["target_today"] for r in rows),
            "recommended_budget_cents": sum(r["decision"]["recommended_budget_cents"] for r in rows),
        },
        "today": {"headline": headline, "screening_id": first["id"], **first["decision"]},
        "screenings": rows,
        "budget": money,
        "curve": [p.model_dump() for p in rules.curve],
        "rules": rules.model_dump(mode="json"),
        "revision": project.revision,
    }
