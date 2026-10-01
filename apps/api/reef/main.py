import csv
import io
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from reef.auth import COOKIE, User, current_user, editor, token_hash, verify_password
from reef.campaigns.service import budget, metrics_for
from reef.config import settings
from reef.db import session
from reef.forecasting.scenarios import scenario_analysis
from reef.integrations.adapters import parse_campaign_csv, parse_ticket_sales_csv, parse_traffic_csv
from reef.intelligence.engine import build_marketing_plan
from reef.models import (
    AuditEvent,
    Campaign,
    CampaignMetric,
    Creative,
    Geography,
    HistoricalSnapshot,
    LoginAttempt,
    LoginSession,
    Project,
    Screening,
    Snapshot,
    TrafficMetric,
    UserAccount,
)
from reef.reports.service import REPORTS, report
from reef.schemas import (
    CampaignInput,
    CampaignStatus,
    CreativeInput,
    Rules,
    RuleUpdate,
    ScenarioInput,
    ScreeningUpdate,
    SnapshotInput,
)
from reef.seed import PROJECT_ID
from reef.ticket_sales.service import dashboard

logger = logging.getLogger("reef")
app = FastAPI(
    title="REEF Launch Intelligence API",
    version="1.0.0",
    docs_url="/docs" if settings().environment != "production" else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def protection(request: Request, call_next):
    request_id = secrets.token_hex(8)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin not in settings().cors_origins.split(","):
            return Response("Origin not allowed", status_code=403)
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 2_100_000:
            return Response("Request exceeds 2 MB", status_code=413)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(IntegrityError)
async def integrity_handler(request, exc):
    return Response(
        '{"detail":"This record already exists or conflicts with a linked record."}',
        status_code=409,
        media_type="application/json",
    )


def project(db: Session, lock: bool = False) -> Project:
    query = select(Project).where(Project.id == PROJECT_ID)
    value = db.scalar(query.with_for_update() if lock else query)
    if not value:
        raise HTTPException(503, "Project is not initialized. Run database migrations and seed.")
    return value


def get(db: Session, model, key):
    row = db.get(model, key)
    if row is None:
        raise HTTPException(404, "Record not found")
    if hasattr(row, "project_id") and row.project_id != PROJECT_ID:
        raise HTTPException(404, "Record not found")
    return row


def audit(db: Session, user: User, action: str, key: str, details: dict):
    db.add(AuditEvent(actor=user.email, action=action, entity_id=key, details=details))


def serialized(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(db: Session = Depends(session)):
    try:
        db.execute(text("SELECT 1"))
        project(db)
    except Exception:
        raise HTTPException(503, "Database unavailable or project not initialized") from None
    return {"status": "ready"}


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=256)


@app.post("/v1/auth/login")
def login(payload: LoginInput, response: Response, db: Session = Depends(session)):
    email = payload.email.strip().casefold()
    now = datetime.now(timezone.utc)
    key = token_hash(email)
    attempts = db.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(LoginAttempt.email_hash == key, LoginAttempt.created_at > now - timedelta(minutes=15))
    )
    if attempts >= 5:
        raise HTTPException(429, "Too many sign-in attempts. Try again in 15 minutes.")
    db.add(LoginAttempt(email_hash=key))
    db.commit()
    account = db.get(UserAccount, email)
    # Always run scrypt, even for unknown accounts, to avoid a cheap identity timing signal.
    fallback = "AAAAAAAAAAAAAAAAAAAAAA=="
    valid = verify_password(payload.password, account.password_hash if account else fallback)
    if not account or not valid or not account.active:
        raise HTTPException(401, "Email or password is incorrect")
    token = secrets.token_urlsafe(48)
    db.add(
        LoginSession(
            token_hash=token_hash(token),
            email=email,
            expires_at=now + timedelta(hours=settings().session_hours),
        )
    )
    db.execute(delete(LoginAttempt).where(LoginAttempt.email_hash == key))
    db.execute(delete(LoginSession).where(LoginSession.expires_at < now))
    db.commit()
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=settings().environment == "production",
        samesite="lax",
        max_age=settings().session_hours * 3600,
        path="/",
    )
    return {"email": email, "role": account.role}


@app.post("/v1/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(session)):
    db.execute(
        delete(LoginSession).where(LoginSession.token_hash == token_hash(request.cookies.get(COOKIE, "")))
    )
    db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"signed_out": True}


@app.get("/v1/auth/me")
def me(user: User = Depends(current_user)):
    return {"email": user.email, "role": user.role, "development": settings().dev_auth_bypass}


@app.get("/v1/dashboard")
def get_dashboard(db: Session = Depends(session), user: User = Depends(current_user)):
    return dashboard(db, project(db))


@app.post("/v1/scenarios")
def scenarios(payload: ScenarioInput, db: Session = Depends(session), user: User = Depends(current_user)):
    p = project(db)
    rules = Rules.model_validate(p.rules)
    try:
        dash = dashboard(db, p)
        result = scenario_analysis(dash, payload, rules)
        result["sales_intelligence"] = dash.get("sales_intelligence")
        result["marketing_plan"] = build_marketing_plan(db, p.id, dash, result, rules)
        return result
    except KeyError as exc:
        raise HTTPException(404, f"Unknown screening: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/v1/history")
def history(db: Session = Depends(session), user: User = Depends(current_user)):
    return {
        "label": "OBSERVED",
        "measure": "Unavailable seats from archived ESO inventory; not verified ticket sales",
        "model_usage": "Reference only; not used to claim paid lift or final attendance",
        "rows": [
            serialized(r)
            for r in db.scalars(select(HistoricalSnapshot).order_by(HistoricalSnapshot.observed_at))
        ],
    }


@app.post("/v1/ticket-sales", status_code=201)
def add_snapshot(payload: SnapshotInput, db: Session = Depends(session), user: User = Depends(editor)):
    screening = get(db, Screening, payload.screening_id)
    if payload.tickets_sold > screening.capacity:
        raise HTTPException(422, "Ticket count exceeds screening capacity")
    if db.scalar(
        select(Snapshot.id).where(
            Snapshot.screening_id == screening.id, Snapshot.observed_at == payload.observed_at
        )
    ):
        raise HTTPException(409, "An observation already exists at this timestamp")
    latest = db.scalar(
        select(Snapshot).where(Snapshot.screening_id == screening.id).order_by(Snapshot.observed_at.desc())
    )
    if (
        latest
        and payload.observed_at > latest.observed_at
        and payload.tickets_sold < latest.tickets_sold
        and not payload.note.strip()
    ):
        raise HTTPException(422, "Add a note explaining refunds or a corrected lower ticket count")
    row = Snapshot(**payload.model_dump(), source_label="OBSERVED", source="manual", created_by=user.email)
    db.add(row)
    audit(db, user, "ticket-observation.created", screening.id, payload.model_dump(mode="json"))
    db.commit()
    return serialized(row)


@app.post("/v1/imports/ticket-sales")
def import_ticket_sales(
    preview: bool = Form(True),
    replace: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(session),
    user: User = Depends(editor),
):
    try:
        rows = parse_ticket_sales_csv(file.file.read(2_000_001))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    screenings = {
        row.id: row
        for row in db.scalars(select(Screening).where(Screening.project_id == PROJECT_ID))
    }
    unknown = sorted({row.screening_id for row in rows if row.screening_id not in screenings})
    if unknown:
        raise HTTPException(422, f"Unknown screening_id: {', '.join(unknown)}")
    for row in rows:
        if row.tickets_sold > screenings[row.screening_id].capacity:
            raise HTTPException(422, f"Ticket count exceeds capacity for {row.screening_id}")
    # Validate decreases within the uploaded series. A note is required for refunds/corrections.
    by_screening: dict[str, list] = {}
    for row in rows:
        by_screening.setdefault(row.screening_id, []).append(row)
    for screening_id, values in by_screening.items():
        values.sort(key=lambda item: item.observed_at)
        previous = db.scalar(
            select(Snapshot)
            .where(Snapshot.screening_id == screening_id, Snapshot.observed_at < values[0].observed_at)
            .order_by(Snapshot.observed_at.desc())
        )
        previous_count = previous.tickets_sold if previous else None
        for row in values:
            if previous_count is not None and row.tickets_sold < previous_count and not row.note.strip():
                raise HTTPException(422, f"Lower ticket count for {screening_id} requires a note")
            previous_count = row.tickets_sold
    existing = {
        (row.screening_id, row.observed_at): row
        for row in db.scalars(select(Snapshot).where(Snapshot.screening_id.in_(list(screenings))))
    }
    conflicts = []
    for row in rows:
        current = existing.get((row.screening_id, row.observed_at))
        if current and (current.tickets_sold != row.tickets_sold or current.note != row.note):
            conflicts.append(f"{row.screening_id}:{row.observed_at.isoformat()}")
    if preview:
        return {"rows": [row.model_dump(mode="json") for row in rows], "conflicts": conflicts, "source_label": "OBSERVED"}
    if conflicts and not replace:
        raise HTTPException(409, "Existing ticket snapshots differ. Preview first and explicitly enable replacement.")
    for row in rows:
        current = existing.get((row.screening_id, row.observed_at))
        if current:
            if replace:
                current.tickets_sold = row.tickets_sold
                current.note = row.note
                current.source = "csv"
                current.source_label = "OBSERVED"
        else:
            db.add(
                Snapshot(
                    **row.model_dump(),
                    source_label="OBSERVED",
                    source="csv",
                    created_by=user.email,
                )
            )
    audit(db, user, "ticket-observations.imported", PROJECT_ID, {"rows": len(rows), "replace": replace})
    db.commit()
    return {"imported": len(rows), "source_label": "OBSERVED"}


@app.put("/v1/screenings/{screening_id}")
def update_screening(
    screening_id: str, payload: ScreeningUpdate, db: Session = Depends(session), user: User = Depends(editor)
):
    row = get(db, Screening, screening_id)
    if payload.sales_open_confirmed and (not payload.sales_open_date or not payload.booking_url):
        raise HTTPException(422, "Confirmed sales opening requires a date and a booking link")
    if payload.sales_open_date and payload.sales_open_date > row.date:
        raise HTTPException(422, "Sales opening must precede the screening")
    for key, value in payload.model_dump(mode="json").items():
        setattr(row, key, value)
    # Date columns require a date object.
    row.sales_open_date = payload.sales_open_date
    audit(db, user, "screening.updated", row.id, payload.model_dump(mode="json"))
    db.commit()
    return serialized(row)


@app.get("/v1/campaigns")
def campaigns(db: Session = Depends(session), user: User = Depends(current_user)):
    return [
        {**serialized(c), "metrics": metrics_for(db, c.id)}
        for c in db.scalars(
            select(Campaign).where(Campaign.project_id == PROJECT_ID).order_by(Campaign.start_date)
        )
    ]


@app.post("/v1/campaigns", status_code=201)
def create_campaign(payload: CampaignInput, db: Session = Depends(session), user: User = Depends(editor)):
    for model, key in [
        (Screening, payload.screening_id),
        (Geography, payload.geography_id),
        (Creative, payload.creative_id),
    ]:
        get(db, model, key)
    screening = get(db, Screening, payload.screening_id)
    if payload.end_date > screening.date:
        raise HTTPException(422, "Campaign cannot end after the associated screening")
    row = Campaign(**payload.model_dump(), project_id=PROJECT_ID, status="DRAFT", created_by=user.email)
    db.add(row)
    db.flush()
    audit(db, user, "campaign.drafted", row.id, {"budget_cents": row.budget_cents})
    db.commit()
    return {**serialized(row), "metrics": metrics_for(db, row.id)}


@app.patch("/v1/campaigns/{campaign_id}/status")
def campaign_status(
    campaign_id: str, payload: CampaignStatus, db: Session = Depends(session), user: User = Depends(editor)
):
    p = project(db, lock=True)
    row = get(db, Campaign, campaign_id)
    rules = Rules.model_validate(p.rules)
    if payload.status == "PAUSED" and row.status not in {"PLANNED", "ACTIVE", "PAUSED"}:
        raise HTTPException(409, "Only an existing committed campaign can be paused")
    if row.status in {"COMPLETED", "CANCELLED"} and payload.status != row.status:
        raise HTTPException(409, "A closed campaign cannot be reactivated; create a new draft")
    if payload.status in {"PLANNED", "ACTIVE"}:
        screen = next(s for s in dashboard(db, p)["screenings"] if s["id"] == row.screening_id)
        if screen["decision"]["status"] not in {"ACTION", "WATCH"} or not screen["booking_url"]:
            raise HTTPException(
                409,
                "Only a current, behind-target screening with a booking link can receive additional spend",
            )
        if screen["days_until"] > rules.paid_window_days:
            raise HTTPException(409, "Screening is outside the paid campaign window")
        if row.status == "DRAFT" and row.start_date < datetime.now(timezone.utc).date():
            raise HTTPException(409, "A new budget commitment cannot start in the past")
        money = budget(db, p.id, rules)
        additional = (
            0
            if row.status in {"PLANNED", "ACTIVE", "PAUSED"}
            else max(0, row.budget_cents - metrics_for(db, row.id)["spend_cents"])
        )
        if additional > min(money["available_cents"], money["channels"][row.platform]["available_cents"]):
            raise HTTPException(409, "Budget ceiling reached; reserve remains protected")
    row.status = payload.status
    audit(db, user, "campaign.status", row.id, {"status": row.status})
    db.commit()
    return {**serialized(row), "notice": "Planning record updated. No advertising platform was changed."}


@app.post("/v1/imports/campaigns")
def import_campaign(
    campaign_id: str = Form(...),
    provider: str = Form(...),
    preview: bool = Form(True),
    replace: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(session),
    user: User = Depends(editor),
):
    campaign = get(db, Campaign, campaign_id)
    if provider not in {campaign.platform, "MANUAL"}:
        raise HTTPException(422, "Provider must match the campaign platform")
    try:
        rows = parse_campaign_csv(file.file.read(2_000_001), provider)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if any(r.date < campaign.start_date or r.date > campaign.end_date for r in rows):
        raise HTTPException(422, "CSV dates must fall within this campaign's start/end dates")
    existing = {
        r.date: r for r in db.scalars(select(CampaignMetric).where(CampaignMetric.campaign_id == campaign.id))
    }
    conflicts = [
        str(r.date)
        for r in rows
        if r.date in existing and any(getattr(existing[r.date], k) != v for k, v in r.model_dump().items())
    ]
    if preview:
        return {
            "rows": [r.model_dump(mode="json") for r in rows],
            "conflicts": conflicts,
            "spend_cents": sum(r.spend_cents for r in rows),
            "source_label": "OBSERVED",
        }
    if conflicts and not replace:
        raise HTTPException(
            409, "Existing dates differ. Review the preview and explicitly enable replacement."
        )
    project(db, lock=True)
    for r in rows:
        if r.date in existing:
            if replace:
                for key, value in r.model_dump().items():
                    setattr(existing[r.date], key, value)
                existing[r.date].source = provider
                existing[r.date].imported_at = datetime.now(timezone.utc)
        else:
            db.add(CampaignMetric(**r.model_dump(), campaign_id=campaign.id, source=provider))
    audit(
        db,
        user,
        "campaign-metrics.imported",
        campaign.id,
        {"provider": provider, "rows": len(rows), "replace": replace},
    )
    db.commit()
    return {"imported": len(rows), "metrics": metrics_for(db, campaign.id)}


@app.post("/v1/imports/traffic")
def import_traffic(
    preview: bool = Form(True),
    replace: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(session),
    user: User = Depends(editor),
):
    try:
        rows = parse_traffic_csv(file.file.read(2_000_001))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    valid_geographies = {
        g.id for g in db.scalars(select(Geography).where(Geography.project_id == PROJECT_ID))
    }
    unknown = sorted({row.geography_id for row in rows if row.geography_id not in valid_geographies})
    if unknown:
        raise HTTPException(422, f"Unknown geography_id: {', '.join(unknown)}")
    existing = {
        (row.geography_id, row.date, row.source): row
        for row in db.scalars(select(TrafficMetric).where(TrafficMetric.project_id == PROJECT_ID))
    }
    conflicts = []
    for row in rows:
        current = existing.get((row.geography_id, row.date, row.source))
        if current and (current.sessions != row.sessions or current.ticket_clicks != row.ticket_clicks):
            conflicts.append(f"{row.date}:{row.geography_id}:{row.source}")
    if preview:
        return {
            "rows": [row.model_dump(mode="json") for row in rows],
            "conflicts": conflicts,
            "sessions": sum(row.sessions for row in rows),
            "ticket_clicks": sum(row.ticket_clicks for row in rows),
            "source_label": "OBSERVED",
        }
    if conflicts and not replace:
        raise HTTPException(409, "Existing traffic rows differ. Preview first and explicitly enable replacement.")
    project(db, lock=True)
    now = datetime.now(timezone.utc)
    for row in rows:
        key = (row.geography_id, row.date, row.source)
        current = existing.get(key)
        if current:
            if replace:
                current.sessions = row.sessions
                current.ticket_clicks = row.ticket_clicks
                current.imported_at = now
        else:
            db.add(
                TrafficMetric(
                    project_id=PROJECT_ID,
                    geography_id=row.geography_id,
                    date=row.date,
                    sessions=row.sessions,
                    ticket_clicks=row.ticket_clicks,
                    source=row.source,
                    imported_at=now,
                )
            )
    audit(
        db,
        user,
        "traffic-metrics.imported",
        PROJECT_ID,
        {"rows": len(rows), "replace": replace},
    )
    db.commit()
    return {"imported": len(rows), "sessions": sum(row.sessions for row in rows), "ticket_clicks": sum(row.ticket_clicks for row in rows)}


def traffic_performance(db: Session, geography_id: str) -> dict:
    rows = list(
        db.scalars(
            select(TrafficMetric).where(
                TrafficMetric.project_id == PROJECT_ID, TrafficMetric.geography_id == geography_id
            )
        )
    )
    sessions = sum(row.sessions for row in rows)
    clicks = sum(row.ticket_clicks for row in rows)
    return {
        "sessions": sessions,
        "ticket_clicks": clicks,
        "ticket_click_rate": round(clicks / sessions * 100, 2) if sessions else None,
        "observations": len(rows),
        "source_label": "OBSERVED" if rows else "UNKNOWN",
        "last_imported_at": max((row.imported_at.isoformat() for row in rows), default=None),
    }


@app.get("/v1/traffic")
def traffic(db: Session = Depends(session), user: User = Depends(current_user)):
    return [
        {"geography_id": g.id, "name": g.name, **traffic_performance(db, g.id)}
        for g in db.scalars(
            select(Geography).where(Geography.project_id == PROJECT_ID).order_by(Geography.min_km)
        )
    ]


@app.get("/v1/creatives")
def creatives(db: Session = Depends(session), user: User = Depends(current_user)):
    return [
        {**serialized(c), "performance": aggregate_metrics(db, "creative_id", c.id)}
        for c in db.scalars(select(Creative).where(Creative.project_id == PROJECT_ID))
    ]


@app.post("/v1/creatives", status_code=201)
def create_creative(payload: CreativeInput, db: Session = Depends(session), user: User = Depends(editor)):
    row = Creative(**payload.model_dump(mode="json"), project_id=PROJECT_ID)
    db.add(row)
    db.flush()
    audit(db, user, "creative.created", row.id, {"name": row.name})
    db.commit()
    return serialized(row)


@app.put("/v1/creatives/{creative_id}")
def update_creative(
    creative_id: str, payload: CreativeInput, db: Session = Depends(session), user: User = Depends(editor)
):
    row = get(db, Creative, creative_id)
    for key, value in payload.model_dump(mode="json").items():
        setattr(row, key, value)
    audit(db, user, "creative.updated", row.id, payload.model_dump(mode="json"))
    db.commit()
    return serialized(row)


def aggregate_metrics(db, field, key):
    values = [
        metrics_for(db, c.id) for c in db.scalars(select(Campaign).where(getattr(Campaign, field) == key))
    ]
    spend = sum(m["spend_cents"] for m in values)
    impressions, clicks = sum(m["impressions"] for m in values), sum(m["clicks"] for m in values)

    def nullable_sum(field):
        found = [m[field] for m in values if m[field] is not None]
        return sum(found) if found else None

    tickets, lpv = nullable_sum("attributed_tickets"), nullable_sum("landing_page_views")
    return {
        "spend_cents": spend,
        "impressions": impressions,
        "clicks": clicks,
        "attributed_tickets": tickets,
        "landing_page_views": lpv,
        "ctr": round(clicks / impressions * 100, 2) if impressions else None,
        "landing_page_response": round(lpv / clicks * 100, 2) if lpv is not None and clicks else None,
        "cost_per_ticket_cents": round(spend / tickets) if tickets else None,
        "observations": sum(m["observations"] for m in values),
    }


@app.get("/v1/geography")
def geography(db: Session = Depends(session), user: User = Depends(current_user)):
    return [
        {
            **serialized(g),
            "performance": aggregate_metrics(db, "geography_id", g.id),
            "traffic": traffic_performance(db, g.id),
        }
        for g in db.scalars(
            select(Geography).where(Geography.project_id == PROJECT_ID).order_by(Geography.min_km)
        )
    ]


@app.get("/v1/integrations")
def integrations(db: Session = Depends(session), user: User = Depends(current_user)):
    return [
        {
            "provider": p,
            "status": (
                "READY" if p == "Manual CSV"
                else "CSV READY" if p in {"Meta Ads", "Google Ads", "Website analytics", "ESO ticket inventory"}
                else "NOT CONNECTED"
            ),
            "label": "PLANNING ASSUMPTION",
            "last_sync": None,
            "detail": detail,
        }
        for p, detail in [
            ("ESO ticket inventory", "Manual entry and batch snapshot CSV import are ready. A live ESO collector still requires a stable public booking-page/API adapter."),
            ("Meta Ads", "CSV import ready. API credentials are not connected."),
            ("Google Ads", "CSV import ready. API credentials are not connected."),
            (
                "Website analytics",
                "Location-level CSV import is ready via /v1/imports/traffic; sessions and ticket-click signals can inform market-test ranking.",
            ),
            ("Manual CSV", "Campaign and location-traffic imports are available. Imported rows are labeled OBSERVED."),
        ]
    ]


@app.put("/v1/rules")
def update_rules(payload: RuleUpdate, db: Session = Depends(session), user: User = Depends(editor)):
    p = project(db, lock=True)
    if p.revision != payload.revision:
        raise HTTPException(409, "Rules changed in another session. Refresh before saving.")
    money = budget(db, p.id, payload.rules)
    if money["over_ceiling"]:
        raise HTTPException(409, "New ceilings would be below recorded spend or commitments")
    previous = p.rules
    p.rules, p.revision = payload.rules.model_dump(mode="json"), p.revision + 1
    audit(db, user, "rules.updated", p.id, {"before": previous, "after": p.rules})
    db.commit()
    return {"rules": p.rules, "revision": p.revision}


@app.get("/v1/audit")
def audit_log(db: Session = Depends(session), user: User = Depends(editor)):
    return [
        serialized(x) for x in db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(50))
    ]


@app.get("/v1/reports/{kind}")
def get_report(
    kind: str, format: str = "json", db: Session = Depends(session), user: User = Depends(current_user)
):
    if kind not in REPORTS:
        raise HTTPException(404, "Unknown report")
    result = report(db, kind, dashboard(db, project(db)))
    if format == "csv":
        output = io.StringIO()
        rows = result["rows"]
        writer = csv.DictWriter(output, fieldnames=list(rows[0]) if rows else ["notice"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: (
                        "'" + str(v)
                        if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r"))
                        else v
                    )
                    for k, v in row.items()
                }
            )
        if not rows:
            writer.writerow({"notice": "No observations available"})
        return Response(
            output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="reef-{kind}.csv"'},
        )
    if format != "json":
        raise HTTPException(422, "Supported formats are json and csv")
    return result
