from datetime import date, timedelta
from math import ceil

from reef.forecasting.engine import curve_target
from reef.schemas import Rules


def decide(
    *,
    sold: int | None,
    days: int,
    stale: bool,
    as_of: date,
    booking_ready: bool,
    sales_open: bool,
    rules: Rules,
) -> dict:
    target = ceil(curve_target(days, rules))
    decision = {
        "status": "PRE_LAUNCH",
        "target_today": target,
        "target_sales_today": max(0, target - ceil(curve_target(days + 1, rules))),
        "recommended_budget_cents": 0,
        "daily_budget_cents": 0,
        "duration_days": rules.campaign_days,
        "channel": "Owned / organic / partners",
        "geography": "Zone A + B · Garching / North Munich",
        "creative": "Creative B — Event",
        "next_review": str(as_of + timedelta(days=1)),
        "action": "Confirm booking links, tracking and the two creative concepts.",
        "reason": "Ticket sales are not confirmed open.",
    }
    if days < 0:
        return {
            **decision,
            "status": "COMPLETE",
            "action": "Reconcile final attendance and record marketing learnings.",
            "reason": "Screening date has passed.",
        }
    if sold is not None and sold >= rules.near_full_tickets:
        return {
            **decision,
            "status": "NEAR_FULL",
            "action": "Stop advertising this screening. Promote the next eligible Tuesday.",
            "reason": f"{sold} tickets observed; stop threshold is {rules.near_full_tickets}.",
        }
    if not sales_open:
        return decision
    if sold is None or stale:
        return {
            **decision,
            "status": "DATA_NEEDED",
            "action": "Update ticket sales before committing advertising budget.",
            "reason": "No current ticket observation. Spend recommendation withheld.",
        }
    ratio = 1 if target == 0 else sold / target
    status = "ON_TRACK" if ratio >= 1 else "WATCH" if ratio >= rules.watch_ratio else "ACTION"
    decision.update(status=status, reason=f"{sold} tickets observed against a target of {target}.")
    if status == "ON_TRACK":
        return {**decision, "action": "Keep organic promotion running. No additional paid spend."}
    if days > rules.paid_window_days:
        return {
            **decision,
            "action": "Use partner and organic promotion; review before the paid campaign window.",
        }
    if not booking_ready:
        return {
            **decision,
            "action": "Confirm a working ticket link before starting a paid campaign.",
            "reason": decision["reason"] + " Booking link missing.",
        }
    daily = rules.watch_daily_cents if status == "WATCH" else rules.action_daily_cents
    duration = min(rules.campaign_days, max(1, days))
    return {
        **decision,
        "daily_budget_cents": daily,
        "recommended_budget_cents": daily * duration,
        "duration_days": duration,
        "channel": "Meta / Instagram / Facebook",
        "action": f"Run a {duration}-day {'local test' if status == 'WATCH' else 'recovery campaign'} using Creative B.",
        "next_review": str(as_of + timedelta(days=duration)),
    }
