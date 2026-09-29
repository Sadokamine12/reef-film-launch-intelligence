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
