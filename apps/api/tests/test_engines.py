from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from reef.forecasting.engine import BookingCurveForecast, ForecastInput, curve_target, sales_velocity
from reef.forecasting.historical import HistoricalRidgeModel
from reef.integrations.adapters import parse_campaign_csv, parse_ticket_sales_csv, parse_traffic_csv
from reef.intelligence.engine import build_sales_intelligence
from reef.marketing.decisions import decide
from reef.schemas import Rules, SnapshotInput


@pytest.mark.parametrize(
    "days,tickets",
    [(60, 8), (45, 15), (30, 25), (21, 38), (14, 55), (7, 75), (3, 88), (0, 98), (61, 0), (-1, 98)],
)
def test_booking_curve(days, tickets):
    assert curve_target(days, Rules()) == tickets


@pytest.mark.parametrize(
    "sold,status,spend",
    [
        (55, "ON_TRACK", 0),
        (44, "WATCH", 2400),
        (43, "ACTION", 6000),
        (95, "NEAR_FULL", 0),
        (100, "NEAR_FULL", 0),
    ],
)
def test_boundaries(sold, status, spend):
    result = decide(
        sold=sold,
        days=14,
        stale=False,
        as_of=date(2027, 1, 19),
        booking_ready=True,
        sales_open=True,
        rules=Rules(),
    )
    assert result["status"] == status
    assert result["recommended_budget_cents"] == spend


@pytest.mark.parametrize(
    "sold,stale,open_,ready,days",
    [
        (None, False, True, True, 14),
        (20, True, True, True, 14),
        (20, False, False, True, 14),
        (20, False, True, False, 14),
        (1, False, True, True, 45),
    ],
)
def test_spend_gates(sold, stale, open_, ready, days):
    assert (
        decide(
            sold=sold,
            days=days,
            stale=stale,
            as_of=date(2027, 1, 19),
            booking_ready=ready,
            sales_open=open_,
            rules=Rules(),
        )["recommended_budget_cents"]
        == 0
    )


def test_velocity_requires_full_window_and_handles_refunds():
    now = datetime(2027, 1, 20, tzinfo=timezone.utc)
    rows = [
        SimpleNamespace(observed_at=now - timedelta(days=d), tickets_sold=n)
        for d, n in [(8, 10), (6, 20), (3, 32), (0, 38)]
    ]
    assert sales_velocity(rows, 3, now) == 2
    assert sales_velocity(rows, 7, now) == pytest.approx(3.29)
    assert sales_velocity(rows[-2:], 7, now) is None
    rows[-1].tickets_sold = 29
    assert sales_velocity(rows, 3, now) == -1


def test_no_forecast_without_current_or_historical_evidence():
    provider = BookingCurveForecast()
    assert provider.predict(ForecastInput(14, 109, None, None, None, False), Rules())["base"] is None


def test_stale_observation_is_retained_as_conservative_floor_without_history():
    pred = BookingCurveForecast().predict(ForecastInput(14, 109, 40, 2, 2, True), Rules())
    assert pred["low"] == pred["base"] == pred["high"] == 40
    assert pred["confidence"] == "LOW"


@pytest.mark.parametrize("sold", range(0, 110, 3))
def test_forecast_bounds(sold):
    pred = BookingCurveForecast().predict(ForecastInput(14, 109, sold, 1, 2, False), Rules())
    assert sold <= pred["low"] <= pred["base"] <= pred["high"] <= 109


def test_invalid_rule_budget():
    with pytest.raises(ValidationError):
        Rules(meta_ceiling_cents=40000)
    with pytest.raises(ValidationError):
        Rules(curve=[{"days": 0, "tickets": 40}, {"days": 10, "tickets": 60}])


def test_future_ticket_observations_rejected():
    with pytest.raises(ValidationError):
        SnapshotInput(
            screening_id="a", observed_at=datetime.now(timezone.utc) + timedelta(days=2), tickets_sold=5
        )


def test_csv_rejects_ambiguous_and_non_eur_data():
    with pytest.raises(ValueError):
        parse_campaign_csv(b"date,spend_eur,impressions,clicks,Currency\n2026-09-01,12.00,20,2,USD", "META")
    with pytest.raises(ValueError):
        parse_campaign_csv(
            b"date,spend_eur,impressions,clicks\n2026-09-01,12.00,20,2\n2026-09-01,1.00,20,2", "META"
        )
    with pytest.raises(ValueError):
        parse_campaign_csv(b"date,spend_eur,impressions,clicks\n2026-09-01,NaN,20,2", "META")


def test_google_generic_conversions_are_not_ticket_sales():
    rows = parse_campaign_csv(b"Day,Cost,Impr.,Clicks,Conversions\n2026-09-01,5.50,1000,30,8", "GOOGLE")
    assert rows[0].spend_cents == 550
    assert rows[0].attributed_tickets is None


def test_manual_ticket_attribution():
    rows = parse_campaign_csv(
        b"date,spend_eur,impressions,clicks,attributed_tickets\n2026-09-01,5.50,1000,30,2", "MANUAL"
    )
    assert rows[0].attributed_tickets == 2


def test_historical_baseline_allows_presales_and_stale_forecasts():
    historical = {
        "low": 35,
        "base": 55,
        "high": 75,
        "range_label": "Bootstrap planning range",
        "evidence": {"method": "historical-ridge-v1"},
        "warnings": ["proxy data"],
    }
    provider = BookingCurveForecast()
    presales = provider.predict(ForecastInput(14, 109, None, None, None, False, historical), Rules())
    assert (presales["low"], presales["base"], presales["high"]) == (35, 55, 75)
    assert presales["source_label"] == "MODEL ESTIMATE"
    assert presales["confidence"] == "LOW"

    stale = provider.predict(ForecastInput(14, 109, 60, None, None, True, historical), Rules())
    assert stale["low"] >= 60
    assert stale["base"] >= 60
    assert stale["high"] >= stale["base"]
    assert "stale" in stale["confidence_note"].lower()


def test_historical_model_groups_repeated_snapshots_by_event():
    rows = []
    events = [
        (date(2026, 10, 14), "https://example.test/a", 35),
        (date(2026, 10, 16), "https://example.test/b", 28),
        (date(2026, 10, 17), "https://example.test/c", 42),
        (date(2026, 10, 18), "https://example.test/d", 48),
    ]
    for show_date, source_url, occupied in events:
        for days_before, delta in [(40, 0), (20, 12)]:
            rows.append(
                SimpleNamespace(
                    show_date=show_date,
                    days_before=days_before,
                    unavailable_seats=occupied + delta,
                    capacity=109,
                    source_url=source_url,
                )
            )
    model = HistoricalRidgeModel(rows)
    metadata = model.metadata()
    assert metadata["rows"] == 8
    assert metadata["unique_events"] == 4
    assert metadata["validation"]["grouping"] == "leave-one-event-out"
    forecast = model.final_forecast(date(2027, 2, 5), 109)
    assert forecast is not None
    assert 0 <= forecast["low"] <= forecast["base"] <= forecast["high"] <= 109
    assert forecast["confidence"] == "LOW"


def test_sales_intelligence_projects_near_term_and_final_from_live_pace():
    rules = Rules(attendance_target_pct=80)
    rows = [{
        "id": "show-a",
        "date": "2027-02-10",
        "capacity": 109,
        "days_until": 14,
        "tickets_sold": 40,
        "sales_open_confirmed": True,
        "sales_open_date": "2026-11-16",
        "stale": False,
        "velocity_3": 2.5,
        "velocity_7": 2.0,
        "forecast": {"low": 60, "base": 75, "high": 90, "confidence": "MEDIUM"},
    }]
    intel = build_sales_intelligence(rows, rules, date(2027, 1, 27))
    row = intel["screenings"][0]
    assert row["final_base"] == 75
    assert row["expected_new_tickets_7d"] > 0
    assert row["expected_cumulative_7d"] >= 40
    assert row["expected_cumulative_14d"] == 75
    assert row["trajectory"][-1]["days"] == 0
    assert row["trajectory"][-1]["base"] == 75
    assert 0 <= row["priority_score"] <= 100


def test_presales_sales_intelligence_marks_near_term_not_applicable_without_opening_evidence():
    rules = Rules()
    rows = [{
        "id": "show-a",
        "date": "2027-02-10",
        "capacity": 109,
        "days_until": 100,
        "tickets_sold": None,
        "sales_open_confirmed": False,
        "sales_open_date": "2026-11-16",
        "stale": False,
        "velocity_3": None,
        "velocity_7": None,
        "forecast": {"low": 30, "base": 50, "high": 70, "confidence": "LOW"},
    }]
    intel = build_sales_intelligence(rows, rules, date(2026, 11, 2))
    row = intel["screenings"][0]
    assert row["expected_new_tickets_7d"] is None
    assert row["expected_new_tickets_14d"] is None
    assert row["sales_state"] == "PRE_SALES"
    assert row["forecast_risk"] == "HIGH"
    assert row["action_urgency"] == "NONE"
    assert row["action_urgency_score"] == 0
    assert row["final_base"] == 50
    assert row["trajectory"][-1]["base"] is None


def test_ticket_snapshot_csv_requires_timezone_and_parses_rows():
    stamp = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    rows = parse_ticket_sales_csv(
        f"screening_id,observed_at,tickets_sold,note\nshow-a,{stamp},4,\n".encode()
    )
    assert rows[0].screening_id == "show-a"
    assert rows[0].tickets_sold == 4
    naive = (datetime.now() - timedelta(minutes=1)).replace(microsecond=0).isoformat()
    with pytest.raises(ValueError):
        parse_ticket_sales_csv(
            f"screening_id,observed_at,tickets_sold\nshow-a,{naive},4\n".encode()
        )


def test_location_traffic_csv_parser():
    rows = parse_traffic_csv(
        b"date,geography_id,sessions,ticket_clicks,source\n2026-09-30,zone-a,100,12,ANALYTICS\n"
    )
    assert rows[0].sessions == 100
    assert rows[0].ticket_clicks == 12
    assert rows[0].source == "ANALYTICS"
