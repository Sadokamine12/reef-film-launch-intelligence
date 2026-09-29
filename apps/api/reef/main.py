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
from reef.integrations.adapters import parse_campaign_csv
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
    UserAccount,
)
from reef.reports.service import REPORTS, report
from reef.schemas import (
    CampaignInput,
    CampaignStatus,
    CreativeInput,
    Rules,
    RuleUpdate,
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
        {**serialized(g), "performance": aggregate_metrics(db, "geography_id", g.id)}
        for g in db.scalars(
            select(Geography).where(Geography.project_id == PROJECT_ID).order_by(Geography.min_km)
        )
    ]


@app.get("/v1/integrations")
def integrations(db: Session = Depends(session), user: User = Depends(current_user)):
    return [
        {
            "provider": p,
            "status": "READY" if p == "Manual CSV" else "NOT CONNECTED",
            "label": "PLANNING ASSUMPTION",
            "last_sync": None,
            "detail": detail,
        }
        for p, detail in [
            ("ESO ticket inventory", "Add official booking links; manual sales observations are supported."),
            ("Meta Ads", "CSV import ready. API credentials are not connected."),
            ("Google Ads", "CSV import ready. API credentials are not connected."),
            (
                "Website analytics",
                "Provider interface prepared; event and ticket attribution schema pending.",
            ),
            ("Manual CSV", "Campaign import available. Imported rows are labeled OBSERVED."),
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
