from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from reef.auth import password_hash
from reef.config import settings
from reef.db import Base, engine, session
from reef.main import app
from reef.models import Screening, Snapshot, UserAccount
from reef.seed import seed
from sqlalchemy.orm import Session


@pytest.fixture(scope="module", autouse=True)
def tables():
    Base.metadata.create_all(engine())
    yield
    engine().dispose()


@pytest.fixture
def db():
    with Session(engine()) as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
        seed(db)
        yield db
        db.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()


@pytest.fixture
def client(db):
    def override():
        try:
            yield db
        except Exception:
            db.rollback()
            raise

    app.dependency_overrides[session] = override
    with TestClient(app, headers={"Origin": "http://localhost:3000"}) as client:
        yield client
    app.dependency_overrides.clear()


def test_seed_and_real_database_dashboard(client):
    r = client.get("/v1/dashboard")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["summary"]["capacity"] == 654
    assert len(data["screenings"]) == 6
    assert [row["date"] for row in data["screenings"]] == [
        "2027-02-02",
        "2027-02-05",
        "2027-02-06",
        "2027-02-09",
        "2027-02-16",
        "2027-02-23",
    ]
    assert data["summary"]["tickets_sold"] is None
    assert data["today"]["recommended_budget_cents"] == 0
    assert len(client.get("/v1/history").json()["rows"]) == 26
    assert data["forecast_model"]["rows"] == 26
    assert data["forecast_model"]["unique_events"] == 13
    assert data["forecast_model"]["validation"]["grouping"] == "leave-one-event-out"
    assert data["forecast_model"]["validation"]["mae_tickets"] > 0
    assert all(row["forecast"]["base"] is not None for row in data["screenings"])
    assert all(row["forecast"]["source_label"] == "MODEL ESTIMATE" for row in data["screenings"])



def test_seed_is_idempotent(db):
    seed(db)
    seed(db)
    rows = db.query(Screening).order_by(Screening.date).all()
    assert len(rows) == 6
    assert sum(row.capacity for row in rows) == 654


def test_snapshot_persists_and_duplicate_rejected(client):
    payload = {
        "screening_id": "resolution-2027-02-02",
        "tickets_sold": 12,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    assert client.post("/v1/ticket-sales", json=payload).status_code == 201
    assert client.post("/v1/ticket-sales", json=payload).status_code == 409
    assert client.get("/v1/dashboard").json()["screenings"][0]["tickets_sold"] == 12
    payload["tickets_sold"] = 8
    payload["observed_at"] = datetime.now(timezone.utc).isoformat()
    assert client.post("/v1/ticket-sales", json=payload).status_code == 422
    payload["note"] = "Two refunded pairs"
    assert client.post("/v1/ticket-sales", json=payload).status_code == 201


def test_capacity_and_future_guard(client, db):
    screening = db.get(Screening, "resolution-2027-02-02")
    screening.capacity = 80
    db.commit()
    payload = {
        "screening_id": "resolution-2027-02-02",
        "tickets_sold": 81,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    assert client.post("/v1/ticket-sales", json=payload).status_code == 422


def test_rules_revision_and_validation(client):
    data = client.get("/v1/dashboard").json()
    payload = {"rules": data["rules"], "revision": data["revision"]}
    assert client.put("/v1/rules", json=payload).status_code == 200
    assert client.put("/v1/rules", json=payload).status_code == 409
    payload["rules"]["total_ceiling_cents"] = 60000
    assert client.put("/v1/rules", json=payload).status_code == 422


def make_campaign(client, **overrides):
    now = date.today()
    payload = {
        "name": "CSV test campaign",
        "platform": "META",
        "geography_id": "zone-a",
        "creative_id": "creative-b",
        "screening_id": "resolution-2027-02-02",
        "start_date": str(now - timedelta(days=4)),
        "end_date": str(now + timedelta(days=4)),
        "budget_cents": 1000,
    }
    payload.update(overrides)
    r = client.post("/v1/campaigns", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_budget_cannot_be_committed_before_sales(client):
    key = make_campaign(client)
    assert client.patch(f"/v1/campaigns/{key}/status", json={"status": "PLANNED"}).status_code == 409
    assert client.get("/v1/dashboard").json()["budget"]["committed_cents"] == 0


def test_csv_preview_import_dedup_and_conflict(client):
    key = make_campaign(client)

    def upload(spend, preview=True, replace=False):
        raw = f"date,spend_eur,impressions,clicks,attributed_tickets\n{date.today()},{spend},100,10,2"
        return client.post(
            "/v1/imports/campaigns",
            data={
                "campaign_id": key,
                "provider": "META",
                "preview": str(preview).lower(),
                "replace": str(replace).lower(),
            },
            files={"file": ("meta.csv", raw, "text/csv")},
        )

    assert upload("9.00").json()["spend_cents"] == 900
    assert client.get("/v1/campaigns").json()[0]["metrics"]["spend_cents"] == 0
    assert upload("9.00", False).status_code == 200
    assert upload("9.00", False).status_code == 200
    assert client.get("/v1/campaigns").json()[0]["metrics"]["spend_cents"] == 900
    assert upload("8.00", False).status_code == 409
    assert upload("8.00", False, True).status_code == 200
    assert client.get("/v1/geography").json()[0]["performance"]["cost_per_ticket_cents"] == 400
    assert client.get("/v1/creatives").json()[1]["performance"]["attributed_tickets"] == 2


def test_reports_csv_sanitizes_formula(client):
    make_campaign(client, name='=HYPERLINK("bad")')
    r = client.get("/v1/reports/campaigns?format=csv")
    assert r.status_code == 200
    assert "'=HYPERLINK" in r.text
    for kind in ["daily", "screenings", "budget", "post-event", "learnings"]:
        assert client.get(f"/v1/reports/{kind}").status_code == 200


def test_origin_rejected(client):
    r = client.post("/v1/ticket-sales", json={}, headers={"Origin": "https://untrusted.example"})
    assert r.status_code == 403


def test_real_login_logout_and_viewer_role(client, db):
    cfg = settings()
    cfg.dev_auth_bypass = False
    try:
        db.add(
            UserAccount(
                email="viewer@reef.test", password_hash=password_hash("Test-password-123"), role="viewer"
            )
        )
        db.commit()
        assert client.get("/v1/dashboard").status_code == 401
        assert (
            client.post("/v1/auth/login", json={"email": "viewer@reef.test", "password": "wrong"}).status_code
            == 401
        )
        r = client.post("/v1/auth/login", json={"email": "viewer@reef.test", "password": "Test-password-123"})
        assert r.status_code == 200, r.text
        assert "HttpOnly" in r.headers["set-cookie"]
        assert client.get("/v1/dashboard").status_code == 200
        assert (
            client.post(
                "/v1/creatives",
                json={"name": "Test", "concept": "Experience", "headline": "test", "body": "test"},
            ).status_code
            == 403
        )
        assert client.post("/v1/auth/logout").status_code == 200
        assert client.get("/v1/dashboard").status_code == 401
    finally:
        cfg.dev_auth_bypass = True


def test_login_rate_limit(client):
    for _ in range(5):
        assert (
            client.post("/v1/auth/login", json={"email": "nobody@reef.test", "password": "bad"}).status_code
            == 401
        )
    assert (
        client.post("/v1/auth/login", json={"email": "nobody@reef.test", "password": "bad"}).status_code
        == 429
    )


def test_global_recommendations_respect_remaining_budget(db):
    from reef.models import Project
    from reef.ticket_sales.service import dashboard

    now = datetime.now(timezone.utc)
    for sid in [
        "resolution-2027-02-02",
        "resolution-2027-02-09",
        "resolution-2027-02-16",
        "resolution-2027-02-23",
    ]:
        s = db.get(Screening, sid)
        s.date = now.date() + timedelta(days=14)
        s.sales_open_date = now.date() - timedelta(days=7)
        s.sales_open_confirmed = True
        s.booking_url = "https://supernova.eso.org/"
        db.add(Snapshot(screening_id=sid, observed_at=now, tickets_sold=1, created_by="test"))
    p = db.get(Project, "resolution-eso-2027")
    p.rules = {**p.rules, "meta_ceiling_cents": 5000, "meta_test_cents": 4000, "google_ceiling_cents": 12500}
    db.commit()
    data = dashboard(db, p, now)
    assert sum(s["decision"]["recommended_budget_cents"] for s in data["screenings"]) <= 5000
    assert data["budget"]["reserve_cents"] == 7500


def test_scenario_default_uses_six_screenings_and_explicit_evidence(client):
    r = client.post("/v1/scenarios", json={})
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["screenings"]) == 6
    assert data["portfolio"]["capacity"] == 654
    assert 0 <= data["portfolio"]["tickets_low"] <= data["portfolio"]["tickets_base"]
    assert data["portfolio"]["tickets_base"] <= data["portfolio"]["tickets_high"] <= 654
    assert data["ticket_price_cents"] == 650
    assert data["evidence"]["price_response"]["classification"] == "PLANNING ASSUMPTION"
    assert data["evidence"]["advertising_response"]["classification"] == "UNKNOWN"
    assert data["portfolio"]["provisional_contribution_cents"] is None


def test_scenario_negative_elasticity_reduces_demand_as_price_rises(client):
    baseline = client.post("/v1/scenarios", json={"ticket_price_cents": 650}).json()
    higher = client.post("/v1/scenarios", json={"ticket_price_cents": 1200}).json()
    assert higher["portfolio"]["tickets_base"] <= baseline["portfolio"]["tickets_base"]
    assert baseline["price_ladder"][0]["ticket_price_cents"] == 650
    assert any(row["ticket_price_cents"] == 1200 for row in higher["price_ladder"])


def test_scenario_break_even_math_uses_capacity_and_cents(client):
    data = client.post(
        "/v1/scenarios",
        json={"screening_ids": ["resolution-2027-02-02"], "ticket_price_cents": 800},
    ).json()
    assert data["screenings"][0]["break_even_tickets_vs_baseline_full"] == 89
    assert 109 * 650 == 70850


def test_ad_budget_needs_explicit_response_assumption(client):
    baseline = client.post("/v1/scenarios", json={"advertising_budget_cents": 0}).json()
    no_response = client.post("/v1/scenarios", json={"advertising_budget_cents": 100000}).json()
    assert no_response["portfolio"]["tickets_base"] == baseline["portfolio"]["tickets_base"]
    assert no_response["portfolio"]["advertising_budget_cents"] == 100000
    assert no_response["evidence"]["advertising_response"]["classification"] == "UNKNOWN"
    assert any("cannot yet be empirically estimated" in warning for warning in no_response["warnings"])


def test_planning_cpa_can_model_capacity_limited_ad_uplift(client):
    baseline = client.post("/v1/scenarios", json={}).json()
    scenario = client.post(
        "/v1/scenarios",
        json={"advertising_budget_cents": 50000, "ad_incremental_cpa_cents": 2500},
    ).json()
    assert scenario["portfolio"]["tickets_base"] >= baseline["portfolio"]["tickets_base"]
    assert scenario["portfolio"]["tickets_base"] <= scenario["portfolio"]["capacity"]
    assert scenario["evidence"]["advertising_response"]["classification"] == "PLANNING ASSUMPTION"


def test_provisional_reef_contribution_requires_complete_economics(client):
    unknown = client.post("/v1/scenarios", json={}).json()
    assert unknown["portfolio"]["reef_ticket_income_cents"] is None
    assert unknown["portfolio"]["provisional_contribution_cents"] is None

    payload = {
        "ticket_price_cents": 1000,
        "advertising_budget_cents": 10000,
        "revenue_share_bps": 5000,
        "fixed_cost_cents": 20000,
        "variable_cost_per_ticket_cents": 100,
    }
    known = client.post("/v1/scenarios", json=payload).json()
    portfolio = known["portfolio"]
    assert portfolio["economics_complete"] is True
    expected_income = round(portfolio["gross_revenue_base_cents"] * 0.5)
    assert portfolio["reef_ticket_income_cents"] == expected_income
    assert portfolio["provisional_contribution_cents"] == (
        expected_income
        - payload["advertising_budget_cents"]
        - payload["fixed_cost_cents"]
        - portfolio["tickets_base"] * payload["variable_cost_per_ticket_cents"]
    )


def test_scenario_rejects_unknown_screening(client):
    r = client.post("/v1/scenarios", json={"screening_ids": ["missing"]})
    assert r.status_code == 404


def test_scenario_includes_dynamic_marketing_and_sales_intelligence(client):
    data = client.post("/v1/scenarios", json={"advertising_budget_cents": 10000}).json()
    assert data["sales_intelligence"]["portfolio"]["final_base"] > 0
    plan = data["marketing_plan"]
    assert len(plan["geographies"]) == 3
    assert [row["rank"] for row in plan["geographies"]] == [1, 2, 3]
    assert sum(row["recommended_budget_cents"] for row in plan["geographies"]) == 10000
    assert all(row["expected_incremental_tickets"] is None for row in plan["geographies"])
    assert len(plan["screenings"]) == 6
    assert sum(row["recommended_budget_cents"] for row in plan["screenings"]) == 10000


def test_geography_ranking_can_change_when_observed_response_arrives(client):
    before = client.post("/v1/scenarios", json={"advertising_budget_cents": 10000}).json()
    assert before["marketing_plan"]["geographies"][0]["id"] == "zone-a"
    key = make_campaign(client, geography_id="zone-c", budget_cents=1000)
    raw = f"date,spend_eur,impressions,clicks,attributed_tickets\n{date.today()},1.00,1000,80,10"
    imported = client.post(
        "/v1/imports/campaigns",
        data={"campaign_id": key, "provider": "META", "preview": "false", "replace": "false"},
        files={"file": ("zone-c.csv", raw, "text/csv")},
    )
    assert imported.status_code == 200, imported.text
    after = client.post("/v1/scenarios", json={"advertising_budget_cents": 10000}).json()
    assert after["marketing_plan"]["geographies"][0]["id"] == "zone-c"
    assert after["marketing_plan"]["geographies"][0]["classification"] == "MODEL ESTIMATE"


def test_planning_cpa_distributes_modeled_increment_without_inventing_extra_total(client):
    data = client.post(
        "/v1/scenarios",
        json={"advertising_budget_cents": 50000, "ad_incremental_cpa_cents": 2500},
    ).json()
    scenario_increment = sum(row["ad_increment_base"] for row in data["screenings"])
    geography_increment = sum(
        row["expected_incremental_tickets"] or 0 for row in data["marketing_plan"]["geographies"]
    )
    assert geography_increment == scenario_increment
