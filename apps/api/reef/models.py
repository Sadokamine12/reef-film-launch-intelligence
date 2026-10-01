from __future__ import annotations

from datetime import date as DateValue
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from reef.db import Base


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    film: Mapped[str] = mapped_column(String(100))
    venue: Mapped[str] = mapped_column(String(200))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Berlin")
    rules: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class Screening(Base):
    __tablename__ = "screenings"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    date: Mapped[DateValue] = mapped_column(Date)
    time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, default=109)
    booking_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sales_open_date: Mapped[DateValue | None] = mapped_column(Date, nullable=True)
    sales_open_confirmed: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (CheckConstraint("capacity > 0"),)


class Snapshot(Base):
    __tablename__ = "ticket_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    screening_id: Mapped[str] = mapped_column(ForeignKey("screenings.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    tickets_sold: Mapped[int] = mapped_column(Integer)
    source_label: Mapped[str] = mapped_column(String(25), default="OBSERVED")
    source: Mapped[str] = mapped_column(String(50), default="manual")
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(200))
    __table_args__ = (UniqueConstraint("screening_id", "observed_at"), CheckConstraint("tickets_sold >= 0"))


class HistoricalSnapshot(Base):
    __tablename__ = "historical_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    programme: Mapped[str] = mapped_column(String(250))
    show_date: Mapped[DateValue] = mapped_column(Date)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    days_before: Mapped[int] = mapped_column(Integer)
    unavailable_seats: Mapped[int] = mapped_column(Integer)
    capacity: Mapped[int] = mapped_column(Integer)
    source_url: Mapped[str] = mapped_column(Text)


class Geography(Base):
    __tablename__ = "geographies"
    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(100))
    min_km: Mapped[int] = mapped_column(Integer)
    max_km: Mapped[int] = mapped_column(Integer)
    priority: Mapped[str] = mapped_column(String(50))
    notes: Mapped[str] = mapped_column(Text)


class TrafficMetric(Base):
    __tablename__ = "traffic_metrics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    geography_id: Mapped[str] = mapped_column(ForeignKey("geographies.id"), index=True)
    date: Mapped[DateValue] = mapped_column(Date, index=True)
    sessions: Mapped[int] = mapped_column(Integer)
    ticket_clicks: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(30), default="MANUAL")
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("project_id", "geography_id", "date", "source"),
        CheckConstraint("sessions >= 0 AND ticket_clicks >= 0"),
    )


class Creative(Base):
    __tablename__ = "creatives"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(150))
    concept: Mapped[str] = mapped_column(String(100))
    headline: Mapped[str] = mapped_column(String(250))
    body: Mapped[str] = mapped_column(Text)
    asset_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    platform: Mapped[str] = mapped_column(String(20))
    ad_set: Mapped[str] = mapped_column(String(150), default="")
    geography_id: Mapped[str] = mapped_column(ForeignKey("geographies.id"))
    audience: Mapped[str] = mapped_column(String(250))
    creative_id: Mapped[str] = mapped_column(ForeignKey("creatives.id"))
    screening_id: Mapped[str] = mapped_column(ForeignKey("screenings.id"))
    start_date: Mapped[DateValue] = mapped_column(Date)
    end_date: Mapped[DateValue] = mapped_column(Date)
    budget_cents: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    external_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_by: Mapped[str] = mapped_column(String(200))
    __table_args__ = (CheckConstraint("budget_cents >= 0"), CheckConstraint("end_date >= start_date"))


class CampaignMetric(Base):
    __tablename__ = "campaign_metrics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    date: Mapped[DateValue] = mapped_column(Date)
    spend_cents: Mapped[int] = mapped_column(Integer)
    impressions: Mapped[int] = mapped_column(Integer)
    clicks: Mapped[int] = mapped_column(Integer)
    landing_page_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attributed_tickets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attribution_note: Mapped[str] = mapped_column(Text, default="Platform attributed; not incremental sales.")
    source: Mapped[str] = mapped_column(String(30))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("campaign_id", "date"),
        CheckConstraint("spend_cents >= 0"),
        CheckConstraint("impressions >= 0 AND clicks >= 0"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON)


class UserAccount(Base):
    __tablename__ = "user_accounts"
    email: Mapped[str] = mapped_column(String(200), primary_key=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    active: Mapped[bool] = mapped_column(default=True)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(ForeignKey("user_accounts.email"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
