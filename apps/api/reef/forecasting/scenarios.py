"""Transparent pricing, advertising, and economics scenario calculations.

This module intentionally separates model evidence from planning assumptions. Historical
ESO inventory can support baseline demand forecasting, but it cannot identify Resolution
price elasticity and currently does not prove incremental advertising lift.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, exp

from reef.schemas import Rules, ScenarioInput

PRICE_LADDER_CENTS = [650, 700, 800, 900, 1000, 1200, 1500]
BUDGET_LADDER_CENTS = [0, 5000, 10000, 25000, 50000, 75000, 100000]


@dataclass(frozen=True)
class ResolvedAssumptions:
    ticket_price_cents: int
    target_pct: float
    elasticity: float
    elasticity_uncertainty: float
    revenue_share_bps: int | None
    fixed_cost_cents: int | None
    variable_cost_cents: int | None
    ad_cpa_cents: int | None
    cannibalization_pct: float | None


def _resolve(payload: ScenarioInput, rules: Rules) -> ResolvedAssumptions:
    return ResolvedAssumptions(
        ticket_price_cents=payload.ticket_price_cents or rules.baseline_ticket_price_cents,
        target_pct=(
            payload.attendance_target_pct
            if payload.attendance_target_pct is not None
            else rules.attendance_target_pct
        ),
        elasticity=(
            payload.price_elasticity
            if payload.price_elasticity is not None
            else rules.price_elasticity
        ),
        elasticity_uncertainty=rules.price_elasticity_uncertainty,
        revenue_share_bps=(
            payload.revenue_share_bps
            if payload.revenue_share_bps is not None
            else rules.revenue_share_bps
        ),
        fixed_cost_cents=(
            payload.fixed_cost_cents if payload.fixed_cost_cents is not None else rules.fixed_cost_cents
        ),
        variable_cost_cents=(
            payload.variable_cost_per_ticket_cents
            if payload.variable_cost_per_ticket_cents is not None
            else rules.variable_cost_per_ticket_cents
        ),
        ad_cpa_cents=(
            payload.ad_incremental_cpa_cents
            if payload.ad_incremental_cpa_cents is not None
            else rules.ad_incremental_cpa_cents
        ),
        cannibalization_pct=(
            payload.cannibalization_pct
            if payload.cannibalization_pct is not None
            else rules.cannibalization_pct
        ),
    )


def _bounded(value: float, capacity: int, observed: int = 0) -> int:
    return min(capacity, max(observed, round(value)))


def _price_multipliers(price_cents: int, baseline_cents: int, elasticity: float, uncertainty: float):
    if price_cents == baseline_cents:
        return 1.0, 1.0, 1.0
    ratio = price_cents / baseline_cents
    exponents = [elasticity - uncertainty, elasticity, min(-0.01, elasticity + uncertainty)]
    candidates = [ratio**value for value in exponents]
    base = ratio**elasticity
    return min(candidates), base, max(candidates)


def _ad_uplift(headroom: int, budget_cents: int, cpa_cents: int | None, cpa_factor: float = 1.0) -> int:
    if headroom <= 0 or budget_cents <= 0 or not cpa_cents:
        return 0
    effective_cpa = max(1.0, cpa_cents * cpa_factor)
    raw_increment = budget_cents / effective_cpa
    # Saturating response: approximately linear for small budgets, then diminishing as seats run out.
    increment = headroom * (1 - exp(-raw_increment / max(headroom, 1)))
    return min(headroom, max(0, round(increment)))


def _allocate_budget(total_budget: int, rows: list[dict]) -> list[int]:
    if total_budget <= 0 or not rows:
        return [0 for _ in rows]
    headrooms = [max(0, row["capacity"] - row["price_base"]) for row in rows]
    total_headroom = sum(headrooms)
    if total_headroom <= 0:
        return [0 for _ in rows]
    allocations = [round(total_budget * value / total_headroom) for value in headrooms]
    difference = total_budget - sum(allocations)
    if allocations:
        allocations[-1] += difference
    return allocations


def _single_screen_price(screening: dict, assumptions: ResolvedAssumptions, rules: Rules) -> dict:
    forecast = screening["forecast"]
    baseline_low = forecast.get("low")
    baseline_base = forecast.get("base")
    baseline_high = forecast.get("high")
    if baseline_base is None:
        raise ValueError(f"Screening {screening['id']} has no baseline forecast")
    observed = screening.get("tickets_sold") or 0
    low_multiplier, base_multiplier, high_multiplier = _price_multipliers(
        assumptions.ticket_price_cents,
        rules.baseline_ticket_price_cents,
        assumptions.elasticity,
        assumptions.elasticity_uncertainty,
    )
    low_source = baseline_low if baseline_low is not None else baseline_base
    high_source = baseline_high if baseline_high is not None else baseline_base
    return {
        "id": screening["id"],
        "date": screening["date"],
        "capacity": screening["capacity"],
        "observed_tickets": screening.get("tickets_sold"),
        "baseline_low": baseline_low,
        "baseline_base": baseline_base,
        "baseline_high": baseline_high,
        "price_low": _bounded(low_source * low_multiplier, screening["capacity"], observed),
        "price_base": _bounded(baseline_base * base_multiplier, screening["capacity"], observed),
        "price_high": _bounded(high_source * high_multiplier, screening["capacity"], observed),
        "forecast_confidence": forecast.get("confidence", "LOW"),
        "forecast_method": forecast.get("method"),
    }


def _apply_budget(rows: list[dict], total_budget: int, cpa_cents: int | None) -> list[dict]:
    allocations = _allocate_budget(total_budget, rows)
    output = []
    for row, allocation in zip(rows, allocations):
        low_headroom = max(0, row["capacity"] - row["price_low"])
        base_headroom = max(0, row["capacity"] - row["price_base"])
        high_headroom = max(0, row["capacity"] - row["price_high"])
        # Planning range around the user/default CPA assumption. A higher CPA is the conservative case.
        ad_low = _ad_uplift(low_headroom, allocation, cpa_cents, 1.25)
        ad_base = _ad_uplift(base_headroom, allocation, cpa_cents, 1.0)
        ad_high = _ad_uplift(high_headroom, allocation, cpa_cents, 0.75)
        predicted_low = min(row["capacity"], row["price_low"] + ad_low)
        predicted_base = max(
            predicted_low, min(row["capacity"], row["price_base"] + ad_base)
        )
        predicted_high = max(
            predicted_base, min(row["capacity"], row["price_high"] + ad_high)
        )
        output.append(
            {
                **row,
                "advertising_budget_cents": allocation,
                "ad_increment_low": ad_low,
                "ad_increment_base": ad_base,
                "ad_increment_high": ad_high,
                "predicted_low": predicted_low,
                "predicted_base": predicted_base,
                "predicted_high": predicted_high,
            }
        )
    return output


def _apply_cannibalization(rows: list[dict], pct: float | None) -> list[dict]:
    if not pct or len(rows) <= 1:
        return rows
    factor = max(0.0, 1.0 - pct / 100.0)
    output = []
    for row in rows:
        observed = row.get("observed_tickets") or 0
        output.append(
            {
                **row,
                "predicted_low": _bounded(row["predicted_low"] * factor, row["capacity"], observed),
                "predicted_base": _bounded(row["predicted_base"] * factor, row["capacity"], observed),
                "predicted_high": _bounded(row["predicted_high"] * factor, row["capacity"], observed),
            }
        )
    return output


def _portfolio(rows: list[dict], assumptions: ResolvedAssumptions, advertising_budget_cents: int) -> dict:
    capacity = sum(row["capacity"] for row in rows)
    low = sum(row["predicted_low"] for row in rows)
    base = sum(row["predicted_base"] for row in rows)
    high = sum(row["predicted_high"] for row in rows)
    gross_low = low * assumptions.ticket_price_cents
    gross_base = base * assumptions.ticket_price_cents
    gross_high = high * assumptions.ticket_price_cents
    share = assumptions.revenue_share_bps
    reef_income = round(gross_base * share / 10000) if share is not None else None
    variable_cost = (
        base * assumptions.variable_cost_cents if assumptions.variable_cost_cents is not None else None
    )
    economics_complete = (
        share is not None
        and assumptions.fixed_cost_cents is not None
        and assumptions.variable_cost_cents is not None
    )
    contribution = None
    if economics_complete and reef_income is not None and variable_cost is not None:
        contribution = (
            reef_income
            - advertising_budget_cents
            - assumptions.fixed_cost_cents
            - variable_cost
        )
    return {
        "capacity": capacity,
        "tickets_low": low,
        "tickets_base": base,
        "tickets_high": high,
        "occupancy_low_pct": round(low / capacity * 100, 1) if capacity else 0,
        "occupancy_base_pct": round(base / capacity * 100, 1) if capacity else 0,
        "occupancy_high_pct": round(high / capacity * 100, 1) if capacity else 0,
        "gross_revenue_low_cents": gross_low,
        "gross_revenue_base_cents": gross_base,
        "gross_revenue_high_cents": gross_high,
        "advertising_budget_cents": advertising_budget_cents,
        "reef_ticket_income_cents": reef_income,
        "variable_cost_cents": variable_cost,
        "fixed_cost_cents": assumptions.fixed_cost_cents,
        "provisional_contribution_cents": contribution,
        "economics_complete": economics_complete,
    }


def _evaluate(
    screenings: list[dict], payload: ScenarioInput, rules: Rules, ticket_price_cents: int
) -> tuple[list[dict], dict, ResolvedAssumptions]:
    local_payload = payload.model_copy(update={"ticket_price_cents": ticket_price_cents})
    assumptions = _resolve(local_payload, rules)
    rows = [_single_screen_price(screening, assumptions, rules) for screening in screenings]
    rows = _apply_budget(rows, payload.advertising_budget_cents, assumptions.ad_cpa_cents)
    rows = _apply_cannibalization(rows, assumptions.cannibalization_pct)
    for row in rows:
        row["occupancy_low_pct"] = round(row["predicted_low"] / row["capacity"] * 100, 1)
        row["occupancy_base_pct"] = round(row["predicted_base"] / row["capacity"] * 100, 1)
        row["occupancy_high_pct"] = round(row["predicted_high"] / row["capacity"] * 100, 1)
        row["gross_revenue_base_cents"] = row["predicted_base"] * assumptions.ticket_price_cents
        row["break_even_tickets_vs_baseline_full"] = ceil(
            row["capacity"] * rules.baseline_ticket_price_cents / assumptions.ticket_price_cents
        )
        row["meets_target"] = row["occupancy_base_pct"] >= assumptions.target_pct
    return rows, _portfolio(rows, assumptions, payload.advertising_budget_cents), assumptions



def _price_sensitivity(
    screenings: list[dict],
    payload: ScenarioInput,
    rules: Rules,
    ladder_prices: list[int],
    dashboard: dict,
) -> dict:
    resolved = _resolve(payload, rules)
    elasticities = sorted(
        {
            max(-5.0, min(-0.01, resolved.elasticity - resolved.elasticity_uncertainty)),
            max(-5.0, min(-0.01, resolved.elasticity)),
            max(-5.0, min(-0.01, resolved.elasticity + resolved.elasticity_uncertainty)),
        }
    )
    cases = []
    winners = []
    for elasticity in elasticities:
        local_payload = payload.model_copy(update={"price_elasticity": elasticity})
        rows = []
        for price in ladder_prices:
            _, result, _ = _evaluate(screenings, local_payload, rules, price)
            rows.append(
                {
                    "ticket_price_cents": price,
                    "tickets_base": result["tickets_base"],
                    "gross_revenue_base_cents": result["gross_revenue_base_cents"],
                    "occupancy_base_pct": result["occupancy_base_pct"],
                }
            )
        winner = max(rows, key=lambda row: row["gross_revenue_base_cents"])
        baseline = next(
            (row for row in rows if row["ticket_price_cents"] == rules.baseline_ticket_price_cents),
            rows[0],
        )
        winners.append(winner["ticket_price_cents"])
        cases.append(
            {
                "elasticity": round(elasticity, 3),
                "winner_price_cents": winner["ticket_price_cents"],
                "winner_revenue_cents": winner["gross_revenue_base_cents"],
                "baseline_revenue_cents": baseline["gross_revenue_base_cents"],
                "winner_gain_cents": winner["gross_revenue_base_cents"] - baseline["gross_revenue_base_cents"],
                "rows": rows,
            }
        )

    same_winner = len(set(winners)) == 1
    candidate = winners[0] if same_winner and winners else None
    min_gain = min((case["winner_gain_cents"] for case in cases), default=0) if candidate else 0
    model_validation = dashboard.get("forecast_model", {}).get("validation", {}) or {}
    mae_tickets = float(model_validation.get("mae_tickets") or 0.0)
    baseline_case = next(
        (row for row in cases[len(cases) // 2]["rows"] if row["ticket_price_cents"] == rules.baseline_ticket_price_cents),
        None,
    ) if cases else None
    baseline_revenue = int(baseline_case["gross_revenue_base_cents"] if baseline_case else 0)
    uncertainty_floor = max(
        round(baseline_revenue * 0.05),
        round(mae_tickets * (candidate or rules.baseline_ticket_price_cents)),
    )
    robust = candidate if candidate is not None and min_gain > uncertainty_floor else None
    if robust is not None:
        message = (
            f"€{robust / 100:.2f} remains the revenue leader across the tested elasticity range and clears the evidence threshold."
        )
        status = "ROBUST_WINNER"
    else:
        message = (
            "No robust revenue-winning price is identified yet. The apparent winner changes with elasticity or its revenue advantage is smaller than the current forecast-uncertainty threshold."
        )
        status = "NO_ROBUST_WINNER"
    return {
        "status": status,
        "robust_revenue_price_cents": robust,
        "scenario_winner_price_cents": candidate if same_winner else None,
        "elasticity_cases": cases,
        "minimum_winner_gain_cents": min_gain,
        "decision_threshold_cents": uncertainty_floor,
        "model_mae_tickets": mae_tickets,
        "message": message,
    }

def scenario_analysis(dashboard: dict, payload: ScenarioInput, rules: Rules) -> dict:
    all_screenings = dashboard["screenings"]
    selected_ids = payload.screening_ids or [row["id"] for row in all_screenings]
    known = {row["id"]: row for row in all_screenings}
    missing = [screening_id for screening_id in selected_ids if screening_id not in known]
    if missing:
        raise KeyError(", ".join(missing))
    screenings = [known[screening_id] for screening_id in selected_ids]
    if not screenings:
        raise ValueError("Select at least one screening")

    assumptions = _resolve(payload, rules)
    rows, portfolio, assumptions = _evaluate(
        screenings, payload, rules, assumptions.ticket_price_cents
    )

    ladder_prices = sorted(set([*PRICE_LADDER_CENTS, assumptions.ticket_price_cents]))
    price_ladder = []
    for price in ladder_prices:
        _, result, local_assumptions = _evaluate(screenings, payload, rules, price)
        price_ladder.append(
            {
                "ticket_price_cents": price,
                "tickets_base": result["tickets_base"],
                "occupancy_base_pct": result["occupancy_base_pct"],
                "gross_revenue_base_cents": result["gross_revenue_base_cents"],
                "meets_target": result["occupancy_base_pct"] >= local_assumptions.target_pct,
            }
        )

    target_candidates = [row for row in price_ladder if row["meets_target"]]
    highest_target_price = (
        max(target_candidates, key=lambda row: row["ticket_price_cents"])["ticket_price_cents"]
        if target_candidates
        else None
    )
    revenue_max = max(price_ladder, key=lambda row: row["gross_revenue_base_cents"])
    price_sensitivity = _price_sensitivity(screenings, payload, rules, ladder_prices, dashboard)

    budget_ladder = []
    for budget in BUDGET_LADDER_CENTS:
        budget_payload = payload.model_copy(update={"advertising_budget_cents": budget})
        _, result, _ = _evaluate(screenings, budget_payload, rules, assumptions.ticket_price_cents)
        budget_ladder.append(
            {
                "advertising_budget_cents": budget,
                "tickets_base": result["tickets_base"],
                "occupancy_base_pct": result["occupancy_base_pct"],
                "gross_revenue_base_cents": result["gross_revenue_base_cents"],
            }
        )

    warnings = [
        "Historical ESO price is effectively constant, so Resolution price elasticity "
        "is not empirically identified.",
        "Price response uses a planning elasticity assumption and must not be interpreted "
        "as measured buyer behaviour.",
        price_sensitivity["message"],
    ]
    if payload.advertising_budget_cents > 0 and assumptions.ad_cpa_cents is None:
        warnings.append(
            "Advertising lift cannot yet be empirically estimated; budget is deducted from "
            "economics but adds no modeled tickets until a planning CPA or empirical response "
            "is supplied."
        )
    elif assumptions.ad_cpa_cents is not None:
        warnings.append(
            "Advertising ticket lift uses an explicit planning CPA with diminishing returns; "
            "it is not causal incrementality evidence."
        )
    if assumptions.cannibalization_pct is None:
        warnings.append("Cross-screening cannibalization is not estimated in the current scenario.")
    else:
        warnings.append("Cannibalization uses a user/planning percentage applied across selected screenings.")
    if assumptions.revenue_share_bps is None:
        warnings.append(
            "REEF revenue share is unknown, so REEF profit/contribution is not reported as factual."
        )

    evidence = {
        "baseline_demand": {
            "classification": "MODEL ESTIMATE",
            "method": dashboard.get("forecast_model", {}).get("method", "historical-ridge-v1"),
            "model": dashboard.get("forecast_model"),
        },
        "ticket_price": {
            "classification": (
                "CONFIRMED FACT"
                if assumptions.ticket_price_cents == rules.baseline_ticket_price_cents
                else "USER INPUT"
            ),
            "baseline_ticket_price_cents": rules.baseline_ticket_price_cents,
        },
        "price_response": {
            "classification": "PLANNING ASSUMPTION",
            "elasticity": assumptions.elasticity,
            "uncertainty": assumptions.elasticity_uncertainty,
            "formula": "demand = baseline_demand * (price / baseline_price) ^ elasticity",
            "robustness_status": price_sensitivity["status"],
            "decision_threshold_cents": price_sensitivity["decision_threshold_cents"],
        },
        "advertising_response": {
            "classification": "PLANNING ASSUMPTION" if assumptions.ad_cpa_cents else "UNKNOWN",
            "incremental_cpa_cents": assumptions.ad_cpa_cents,
            "method": (
                "CPA planning assumption with capacity-constrained diminishing returns"
                if assumptions.ad_cpa_cents
                else None
            ),
        },
        "economics": {
            "classification": "USER INPUT" if assumptions.revenue_share_bps is not None else "UNKNOWN",
            "revenue_share_bps": assumptions.revenue_share_bps,
            "fixed_cost_cents": assumptions.fixed_cost_cents,
            "variable_cost_per_ticket_cents": assumptions.variable_cost_cents,
        },
        "cannibalization": {
            "classification": (
                "PLANNING ASSUMPTION"
                if assumptions.cannibalization_pct is not None
                else "UNKNOWN"
            ),
            "pct": assumptions.cannibalization_pct,
        },
    }

    return {
        "screening_ids": selected_ids,
        "ticket_price_cents": assumptions.ticket_price_cents,
        "baseline_ticket_price_cents": rules.baseline_ticket_price_cents,
        "attendance_target_pct": assumptions.target_pct,
        "advertising_budget_cents": payload.advertising_budget_cents,
        "screenings": rows,
        "portfolio": portfolio,
        "price_ladder": price_ladder,
        "budget_ladder": budget_ladder,
        "highest_tested_price_meeting_target_cents": highest_target_price,
        "revenue_maximizing_tested_price_cents": revenue_max["ticket_price_cents"],
        "price_sensitivity": price_sensitivity,
        "robust_revenue_price_cents": price_sensitivity["robust_revenue_price_cents"],
        "price_decision": {
            "status": price_sensitivity["status"],
            "scenario_winner_price_cents": revenue_max["ticket_price_cents"],
            "robust_revenue_price_cents": price_sensitivity["robust_revenue_price_cents"],
            "message": price_sensitivity["message"],
        },
        "evidence": evidence,
        "warnings": warnings,
    }
