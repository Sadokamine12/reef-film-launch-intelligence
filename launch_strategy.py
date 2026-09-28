"""Business-first ticket-sales and marketing rules for Resolution @ ESO.

The module intentionally separates operational decisions from model internals. It can
use live Resolution booking snapshots when they exist, but it also provides a clear
pre-launch plan before ticket sales are public.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd


DEFAULT_CURVE = {
    60: 8,
    45: 15,
    30: 25,
    21: 38,
    14: 55,
    7: 75,
    3: 88,
    0: 98,
}


def berlin_today() -> date:
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


def _date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def launch_cfg(cfg: dict) -> dict:
    base = {
        "sales_open_target": "2026-11-16",
        "paid_test_start": "2027-01-04",
        "paid_test_end": "2027-01-10",
        "initial_test_budget_eur": 100,
        "meta_budget_ceiling_eur": 300,
        "google_budget_ceiling_eur": 125,
        "tactical_reserve_eur": 75,
        "target_final_tickets_per_show": 98,
        "review_hours_after_sales_open": 48,
        "target_curve": {str(k): v for k, v in DEFAULT_CURVE.items()},
    }
    base.update(cfg.get("launch_plan", {}))
    return base


def target_curve(cfg: dict) -> dict[int, int]:
    raw = launch_cfg(cfg).get("target_curve", {})
    curve = {int(k): int(v) for k, v in raw.items()}
    return curve or DEFAULT_CURVE.copy()


def target_tickets(days_to_show: int, cfg: dict) -> int:
    """Interpolate the management booking curve for one screening."""
    capacity = int(cfg["venue"].get("capacity_per_show", 109))
    curve = target_curve(cfg)
    points = sorted(curve.items(), reverse=True)

    if days_to_show >= points[0][0]:
        return max(0, min(capacity, points[0][1]))
    if days_to_show <= points[-1][0]:
        return max(0, min(capacity, points[-1][1]))

    for (d_hi, t_hi), (d_lo, t_lo) in zip(points, points[1:]):
        if d_hi >= days_to_show >= d_lo:
            span = d_hi - d_lo
            fraction = (d_hi - days_to_show) / span if span else 0
            value = t_hi + fraction * (t_lo - t_hi)
            return max(0, min(capacity, int(round(value))))
    return 0


def booking_curve_frame(cfg: dict) -> pd.DataFrame:
    curve = target_curve(cfg)
    return pd.DataFrame(
        [{"days_before_show": day, "target_tickets": tickets} for day, tickets in sorted(curve.items(), reverse=True)]
    )


def _latest_sales_by_show(resolution: pd.DataFrame, cfg: dict) -> dict[str, dict]:
    if resolution is None or resolution.empty:
        return {}
    required = {"show_date", "tickets_sold", "collected_at"}
    if not required.issubset(resolution.columns):
        return {}

    data = resolution.copy()
    if "status" in data.columns:
        data = data[data["status"].astype(str).str.startswith("ok")]
    data["show_key"] = pd.to_datetime(data["show_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    data["collected_ts"] = pd.to_datetime(data["collected_at"], utc=True, errors="coerce")
    data["tickets_sold"] = pd.to_numeric(data["tickets_sold"], errors="coerce")
    data = data.dropna(subset=["show_key", "collected_ts", "tickets_sold"])
    if data.empty:
        return {}

    out: dict[str, dict] = {}
    for show_key, group in data.groupby("show_key"):
        group = group.sort_values("collected_ts")
        latest = group.iloc[-1]
        latest_ts = latest["collected_ts"]
        recent = group[group["collected_ts"] >= latest_ts - pd.Timedelta(days=7)]
        pace = None
        if len(recent) >= 2:
            first = recent.iloc[0]
            elapsed = max((latest_ts - first["collected_ts"]).total_seconds() / 86400.0, 0.25)
            pace = max(0.0, float(latest["tickets_sold"] - first["tickets_sold"]) / elapsed)
        out[str(show_key)] = {
            "sold": int(round(float(latest["tickets_sold"]))),
            "pace_7d": pace,
            "collected_at": latest_ts,
        }
    return out


def _status(sold: int, target: int) -> str:
    if target <= 0 or sold >= target:
        return "ON TRACK"
    ratio = sold / max(target, 1)
    if ratio >= 0.80:
        return "WATCH"
    return "ACTION"


def _daily_budget(status: str, days_to_show: int) -> int:
    if status == "ON TRACK":
        return 0
    if status == "WATCH":
        return 8 if days_to_show > 14 else 12
    if days_to_show > 21:
        return 15
    if days_to_show > 7:
        return 20
    return 25


def _forecast(sold: int, target: int, pace: float | None, days_to_show: int, cfg: dict) -> tuple[int, int, int]:
    capacity = int(cfg["venue"].get("capacity_per_show", 109))
    final_target = int(launch_cfg(cfg).get("target_final_tickets_per_show", 98))
    curve_projection = final_target * (sold / max(target, 1)) if target > 0 else sold
    if pace is None:
        mid = curve_projection
    else:
        pace_projection = sold + pace * max(days_to_show, 0)
        mid = 0.65 * curve_projection + 0.35 * pace_projection
    mid = max(sold, min(capacity, int(round(mid))))
    width = max(7, min(20, int(round(6 + max(days_to_show, 0) * 0.20))))
    low = max(sold, mid - width)
    high = min(capacity, mid + width)
    return low, mid, high


def show_plan(cfg: dict, resolution: pd.DataFrame | None = None, as_of: date | None = None) -> pd.DataFrame:
    """Return the management plan for each Resolution screening."""
    as_of = as_of or berlin_today()
    plan = launch_cfg(cfg)
    sales_open = _date(plan["sales_open_target"])
    paid_start = _date(plan["paid_test_start"])
    latest = _latest_sales_by_show(resolution if resolution is not None else pd.DataFrame(), cfg)
    rows: list[dict] = []

    for raw_show in cfg["screenings"].get("dates", []):
        show = _date(raw_show)
        show_key = show.isoformat()
        days = (show - as_of).days
        live = latest.get(show_key)

        if as_of < sales_open:
            rows.append({
                "show_date": show_key,
                "days_to_show": days,
                "sold": None,
                "target_today": None,
                "gap": None,
                "pace_7d": None,
                "forecast_low": None,
                "forecast_mid": None,
                "forecast_high": None,
                "status": "PRE-LAUNCH",
                "daily_budget": 0,
                "recommended_action": "Prepare booking launch, tracking and creative. No paid spend yet.",
                "channel": "Organic / partner channels",
                "area": "ESO + Garching + Munich launch audience",
            })
            continue

        if live is None:
            rows.append({
                "show_date": show_key,
                "days_to_show": days,
                "sold": None,
                "target_today": target_tickets(days, cfg),
                "gap": None,
                "pace_7d": None,
                "forecast_low": None,
                "forecast_mid": None,
                "forecast_high": None,
                "status": "WAITING FOR DATA",
                "daily_budget": 0,
                "recommended_action": "Connect the ESO booking URL and collect a 48-hour sales baseline.",
                "channel": "Tracking setup",
                "area": "All four booking pages",
            })
            continue

        sold = int(live["sold"])
        target = target_tickets(days, cfg)
        gap = max(target - sold, 0)
        status = _status(sold, target)
        budget = _daily_budget(status, days)
        if as_of < paid_start:
            budget = 0
        low, mid, high = _forecast(sold, target, live.get("pace_7d"), days, cfg)

        if as_of < paid_start and status != "ON TRACK":
            action = "Keep paid media off until the planned test window; improve organic distribution and verify tracking."
            channel = "Organic / owned / partner"
        elif status == "ON TRACK":
            action = "No extra paid spend. Protect budget and keep monitoring daily sales pace."
            channel = "Organic + retargeting only if needed"
        elif status == "WATCH":
            action = "Run a small 72-hour correction, then re-check sales before spending more."
            channel = "Meta first; Google Search for high intent"
        else:
            action = "Run a 72-hour recovery campaign now and re-check the booking curve before the next spend decision."
            channel = "Meta + Google Search"

        rows.append({
            "show_date": show_key,
            "days_to_show": days,
            "sold": sold,
            "target_today": target,
            "gap": gap,
            "pace_7d": live.get("pace_7d"),
            "forecast_low": low,
            "forecast_mid": mid,
            "forecast_high": high,
            "status": status,
            "daily_budget": budget,
            "recommended_action": action,
            "channel": channel,
            "area": "0–30 km from ESO / north Munich; expand to 30–50 km only if efficient",
        })

    return pd.DataFrame(rows)


def today_decision(plan_df: pd.DataFrame, cfg: dict, as_of: date | None = None) -> dict:
    as_of = as_of or berlin_today()
    plan = launch_cfg(cfg)
    sales_open = _date(plan["sales_open_target"])
    paid_start = _date(plan["paid_test_start"])

    if as_of < sales_open:
        days = (sales_open - as_of).days
        return {
            "status": "PRE-LAUNCH",
            "headline": "Spend €0 today — prepare the ticket-sales launch",
            "detail": f"Target ticket-sales opening: {sales_open.strftime('%d %b %Y')} ({days} days). Prepare booking links, UTMs, two creatives and local listings now.",
            "budget": 0,
            "channel": "Owned / organic / partner preparation",
            "area": "Garching + north Munich launch audience",
            "review": f"First sales review: {int(plan['review_hours_after_sales_open'])} hours after booking opens",
        }

    if plan_df.empty or plan_df["sold"].notna().sum() == 0:
        return {
            "status": "WAITING FOR DATA",
            "headline": "Connect the ESO booking pages before spending",
            "detail": "Collect at least 48 hours of Resolution sales movement so the campaign has a real baseline.",
            "budget": 0,
            "channel": "Tracking setup",
            "area": "All four show booking pages",
            "review": "48 hours after the first valid booking snapshot",
        }

    rank = {"ACTION": 0, "WATCH": 1, "ON TRACK": 2, "WAITING FOR DATA": 3, "PRE-LAUNCH": 4}
    active = plan_df[plan_df["days_to_show"] >= 0].copy()
    if active.empty:
        return {
            "status": "COMPLETE",
            "headline": "Campaign complete",
            "detail": "All scheduled Resolution screenings are in the past.",
            "budget": 0,
            "channel": "None",
            "area": "None",
            "review": "Post-campaign review",
        }
    active["status_rank"] = active["status"].map(rank).fillna(9)
    active = active.sort_values(["status_rank", "show_date"])
    row = active.iloc[0]
    show_label = pd.Timestamp(row["show_date"]).strftime("%d %b")
    budget = int(row["daily_budget"] or 0)

    if row["status"] == "ACTION":
        headline = f"Recover the {show_label} screening: €{budget}/day for 3 days"
    elif row["status"] == "WATCH":
        headline = f"Correct the {show_label} screening: €{budget}/day for 3 days"
    else:
        headline = f"{show_label} is on track — spend €0 extra today"

    if as_of < paid_start:
        headline = "Keep paid media off until the planned test window"
        budget = 0

    return {
        "status": str(row["status"]),
        "headline": headline,
        "detail": str(row["recommended_action"]),
        "budget": budget,
        "channel": str(row["channel"]),
        "area": str(row["area"]),
        "review": "Re-check in 72 hours after any paid change, otherwise review daily",
    }


def marketing_timeline(cfg: dict) -> pd.DataFrame:
    plan = launch_cfg(cfg)
    return pd.DataFrame([
        {
            "Period": "Now → 15 Nov 2026",
            "Goal": "Launch readiness",
            "Paid ceiling": "€0",
            "What to do": "Confirm ESO ticket launch, booking URLs, UTMs, event listings and two ad creatives.",
        },
        {
            "Period": "16 Nov 2026 → 3 Jan 2027",
            "Goal": "Organic baseline",
            "Paid ceiling": "€0",
            "What to do": "Sell tickets through ESO/REEF/partners and learn the natural booking pace before paid media.",
        },
        {
            "Period": "4 → 10 Jan 2027",
            "Goal": "Controlled paid test",
            "Paid ceiling": f"€{int(plan['initial_test_budget_eur'])}",
            "What to do": "Meta €70 + Google €30. Test two creative angles and local catchment response.",
        },
        {
            "Period": "11 → 31 Jan 2027",
            "Goal": "Conditional scaling",
            "Paid ceiling": "Only if behind curve",
            "What to do": "Move budget only to shows/areas/channels that need help; pause shows already on track.",
        },
        {
            "Period": "1 → 23 Feb 2027",
            "Goal": "Show-specific recovery",
            "Paid ceiling": "€8–€25/day when triggered",
            "What to do": "Advertise the specific Tuesday that is behind. Stop promoting a show once it is near target/capacity.",
        },
    ])


def geography_plan() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Zone": "A — Core",
            "Distance": "0–15 km from ESO",
            "Priority": "Highest",
            "Paid reach guide": "50%",
            "Use": "Garching, research campus, U6/north-Munich catchment",
        },
        {
            "Zone": "B — Munich catchment",
            "Distance": "15–30 km",
            "Priority": "High",
            "Paid reach guide": "35%",
            "Use": "Munich + nearby north/east catchment; scale only when Zone A has enough delivery",
        },
        {
            "Zone": "C — Expansion",
            "Distance": "30–50 km",
            "Priority": "Test only",
            "Paid reach guide": "15%",
            "Use": "Use only if the nearer zones are efficient and a show still needs demand",
        },
    ])


def channel_budget(cfg: dict) -> pd.DataFrame:
    plan = launch_cfg(cfg)
    return pd.DataFrame([
        {"Channel": "Meta — Instagram + Facebook", "Ceiling": int(plan["meta_budget_ceiling_eur"]), "Role": "Discovery, trailer, Reels/Stories, retargeting"},
        {"Channel": "Google Search", "Ceiling": int(plan["google_budget_ceiling_eur"]), "Role": "Capture high-intent event/planetarium searches"},
        {"Channel": "Tactical reserve", "Ceiling": int(plan["tactical_reserve_eur"]), "Role": "Only for the best-performing need/winner late in the campaign"},
    ])


def creative_plan() -> pd.DataFrame:
    return pd.DataFrame([
        {"Creative": "A — Experience", "Message": "Immersive music + light + dome experience", "Use": "Broad discovery / Reels / Stories"},
        {"Creative": "B — Event", "Message": "Resolution at ESO Supernova — exact Tuesday + Garching/U6 + ticket CTA", "Use": "High-intent local event conversion"},
    ])
