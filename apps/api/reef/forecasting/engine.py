"""Replaceable prediction interface. v1 is an uncalibrated planning estimate, not learned lift."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from typing import Protocol

from reef.schemas import Rules


def curve_target(days: int, rules: Rules) -> float:
    points = sorted(rules.curve, key=lambda p: p.days)
    if days <= 0:
        return float(points[0].tickets)
    if days > points[-1].days:
        return 0.0  # No management target before the defined curve begins.
    for left, right in zip(points, points[1:]):
        if left.days <= days <= right.days:
            return round(
                left.tickets + (right.tickets - left.tickets) * (days - left.days) / (right.days - left.days),
                2,
            )
    return float(points[-1].tickets)


def sales_velocity(snapshots: list, window: int, as_of: datetime) -> float | None:
    """Interpolate only between observed points; never extrapolate a short history into a full window."""
    rows = sorted((s for s in snapshots if s.observed_at <= as_of), key=lambda s: s.observed_at)
    if len(rows) < 2:
        return None
    latest = rows[-1]
    cutoff = latest.observed_at - timedelta(days=window)
    earlier = [s for s in rows if s.observed_at <= cutoff]
    later = [s for s in rows if s.observed_at >= cutoff]
    if not earlier or not later:
        return None
    a, b = earlier[-1], later[0]
    span = (b.observed_at - a.observed_at).total_seconds()
    interpolated = (
        a.tickets_sold
        if span == 0
        else a.tickets_sold
        + (b.tickets_sold - a.tickets_sold) * (cutoff - a.observed_at).total_seconds() / span
    )
    return round((latest.tickets_sold - interpolated) / window, 2)


@dataclass
class ForecastInput:
    days: int
    capacity: int
    sold: int | None
    velocity_3: float | None
    velocity_7: float | None
    stale: bool


class ForecastProvider(Protocol):
    def predict(self, values: ForecastInput, rules: Rules) -> dict: ...


class BookingCurveForecast:
    def predict(self, values: ForecastInput, rules: Rules) -> dict:
        target = min(values.capacity, curve_target(0, rules))
        today = curve_target(values.days, rules)
        required = (
            None if values.sold is None else round(max(0, target - values.sold) / max(values.days, 1), 2)
        )
        common = {
            "required_sales_pace": required,
            "gap_to_target": None if values.sold is None else max(0, ceil(today - values.sold)),
            "source_label": "ESTIMATED",
            "method": "booking-curve-v1",
            "confidence": "LOW",
            "confidence_note": "Planning range; not a calibrated prediction interval.",
        }
        if values.sold is None or values.stale:
            return {
                **common,
                "low": None,
                "base": None,
                "high": None,
                "confidence_note": "A current ticket observation is required.",
            }
        sold = values.sold
        curve_projection = max(sold, target + sold - today)
        pace = values.velocity_3 if values.velocity_3 is not None else values.velocity_7
        projected = (
            curve_projection
            if pace is None
            else 0.55 * curve_projection + 0.45 * (sold + max(0, pace) * max(0, values.days))
        )
        base = min(values.capacity, max(sold, round(projected)))
        if values.days <= 0:
            # On show day the observed count is the conservative estimate. Final reconciliation is separate.
            base = sold
        width = max(5, round(values.capacity * (0.20 if pace is None else 0.12)))
        return {
            **common,
            "low": max(sold, base - width),
            "base": base,
            "high": min(values.capacity, base + width),
            "confidence": "LOW" if pace is None else "MEDIUM",
            "confidence_note": "Heuristic estimate; not validated against final Resolution attendance.",
        }
