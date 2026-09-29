"""Small-data historical demand model with grouped validation and no native ML dependency.

The archived ESO rows are repeated booking-page inventory snapshots. They are useful as a
booking-demand proxy, but they are not verified final attendance. The model therefore keeps
its outputs deliberately transparent and labels final attendance as an extrapolation.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from random import Random
from statistics import mean
from typing import Iterable


RIDGE_LAMBDA = 10.0
BOOTSTRAP_SAMPLES = 200
BOOTSTRAP_SEED = 202702


@dataclass(frozen=True)
class HistoricalPoint:
    group: str
    days_before: int
    occupied: int
    capacity: int
    weekend: bool
    source_url: str
    weekday: str

    @property
    def occupancy(self) -> float:
        return self.occupied / self.capacity


def _point(row) -> HistoricalPoint:
    show_date = row.show_date
    return HistoricalPoint(
        group=f"{row.source_url}|{show_date.isoformat()}",
        days_before=int(row.days_before),
        occupied=int(row.unavailable_seats),
        capacity=int(row.capacity),
        weekend=show_date.weekday() >= 4,  # Friday, Saturday, Sunday
        source_url=row.source_url,
        weekday=show_date.strftime("%A"),
    )


def _features(days_before: int, weekend: bool) -> list[float]:
    # Scaling keeps the tiny normal-equation system numerically well behaved.
    days = days_before / 90.0
    return [1.0, days, days * days, 1.0 if weekend else 0.0]


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve a tiny dense system using Gauss-Jordan elimination."""
    size = len(vector)
    augmented = [matrix[i][:] + [vector[i]] for i in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        if abs(divisor) < 1e-12:
            raise ValueError("Historical ridge system is singular")
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                augmented[row][index] - factor * augmented[column][index]
                for index in range(size + 1)
            ]
    return [augmented[index][-1] for index in range(size)]


def _fit(points: list[HistoricalPoint], ridge_lambda: float = RIDGE_LAMBDA) -> list[float]:
    width = 4
    matrix = [[0.0 for _ in range(width)] for _ in range(width)]
    vector = [0.0 for _ in range(width)]
    for point in points:
        x = _features(point.days_before, point.weekend)
        target = point.occupancy
        for i in range(width):
            vector[i] += x[i] * target
            for j in range(width):
                matrix[i][j] += x[i] * x[j]
    # Keep the intercept unpenalized; shrink small-sample shape/day-type effects strongly.
    for index in range(1, width):
        matrix[index][index] += ridge_lambda
    return _solve(matrix, vector)


def _predict_occupancy(coefficients: list[float], days_before: int, weekend: bool) -> float:
    value = sum(
        coefficient * feature
        for coefficient, feature in zip(coefficients, _features(days_before, weekend), strict=True)
    )
    return min(1.0, max(0.0, value))


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot compute percentile of empty data")
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


class HistoricalRidgeModel:
    """Transparent ridge model trained on archived ESO booking inventory snapshots."""

    def __init__(self, rows: Iterable):
        self.points = [_point(row) for row in rows if row.capacity and row.capacity > 0]
        self.groups: dict[str, list[HistoricalPoint]] = defaultdict(list)
        for point in self.points:
            self.groups[point.group].append(point)
        self.coefficients = _fit(self.points) if self.available else None
        self.validation = self._validate() if self.available else None

    @property
    def available(self) -> bool:
        return len(self.points) >= 8 and len(self.groups) >= 4

    def _validate(self) -> dict:
        ticket_errors: list[float] = []
        occupancy_errors: list[float] = []
        # Leave-one-event-out validation prevents repeated snapshots of one screening leaking
        # into both train and validation data.
        for group in sorted(self.groups):
            train = [point for point in self.points if point.group != group]
            if len({point.group for point in train}) < 3:
                continue
            coefficients = _fit(train)
            for point in self.groups[group]:
                occupancy = _predict_occupancy(coefficients, point.days_before, point.weekend)
                predicted = occupancy * point.capacity
                ticket_errors.append(abs(predicted - point.occupied))
                occupancy_errors.append(abs(occupancy - point.occupancy) * 100)
        return {
            "grouping": "leave-one-event-out",
            "mae_tickets": round(mean(ticket_errors), 2) if ticket_errors else None,
            "mae_occupancy_pp": round(mean(occupancy_errors), 2) if occupancy_errors else None,
        }

    def metadata(self) -> dict:
        if not self.available:
            return {
                "available": False,
                "method": "historical-ridge-v1",
                "rows": len(self.points),
                "unique_events": len(self.groups),
                "warning": "Not enough historical events to fit the baseline model.",
            }
        days = [point.days_before for point in self.points]
        return {
            "available": True,
            "method": "historical-ridge-v1",
            "model_type": "ridge regression",
            "ridge_lambda": RIDGE_LAMBDA,
            "features": ["days_to_event", "days_to_event_squared", "fri_sat_sun_indicator"],
            "rows": len(self.points),
            "unique_events": len(self.groups),
            "observed_days_range": [min(days), max(days)],
            "observed_weekdays": sorted({point.weekday for point in self.points}),
            "validation": self.validation,
            "target": "unavailable booking inventory as a demand proxy",
            "sources": sorted({point.source_url for point in self.points}),
            "limitations": [
                "Archived ESO inventory is not verified ticket sales or final attendance.",
                "Validation measures snapshot prediction at observed lead times, not final attendance calibration.",
                "Final attendance is extrapolated beyond the historical lead-time range.",
                "Historical price is effectively constant, so this model does not estimate price elasticity.",
            ],
        }

    def _bootstrap_predictions(self, show_date: date, capacity: int) -> list[float]:
        groups = sorted(self.groups)
        rng = Random(BOOTSTRAP_SEED + show_date.toordinal())
        values: list[float] = []
        weekend = show_date.weekday() >= 4
        for _ in range(BOOTSTRAP_SAMPLES):
            sampled: list[HistoricalPoint] = []
            for _ in groups:
                sampled.extend(self.groups[rng.choice(groups)])
            try:
                coefficients = _fit(sampled)
            except ValueError:
                continue
            values.append(_predict_occupancy(coefficients, 0, weekend) * capacity)
        return values

    def final_forecast(self, show_date: date, capacity: int) -> dict | None:
        if not self.available or self.coefficients is None:
            return None
        weekend = show_date.weekday() >= 4
        base_value = _predict_occupancy(self.coefficients, 0, weekend) * capacity
        bootstrapped = self._bootstrap_predictions(show_date, capacity)
        cv_width = float(self.validation.get("mae_tickets") or capacity * 0.2)
        bootstrap_low = _percentile(bootstrapped, 0.10) if bootstrapped else base_value
        bootstrap_high = _percentile(bootstrapped, 0.90) if bootstrapped else base_value
        width_low = max(cv_width, base_value - bootstrap_low)
        width_high = max(cv_width, bootstrap_high - base_value)
        base = min(capacity, max(0, round(base_value)))
        low = min(base, max(0, round(base_value - width_low)))
        high = max(base, min(capacity, round(base_value + width_high)))
        observed_weekdays = {point.weekday for point in self.points}
        weekday = show_date.strftime("%A")
        warnings = [
            "Final attendance is an extrapolation: historical snapshots stop before show day.",
            "Historical inventory is a booking-demand proxy, not verified final attendance.",
        ]
        if weekday not in observed_weekdays:
            warnings.append(
                f"{weekday} is not present in the historical archive; the model uses its broader weekday class."
            )
        return {
            "low": low,
            "base": base,
            "high": high,
            "confidence": "LOW",
            "range_label": "Bootstrap planning range",
            "evidence": self.metadata(),
            "warnings": warnings,
        }
