from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CurvePoint(StrictModel):
    days: int = Field(ge=0, le=365)
    tickets: int = Field(ge=0, le=109)


class Rules(StrictModel):
    curve: list[CurvePoint] = [
        CurvePoint(days=d, tickets=t)
        for d, t in [(60, 8), (45, 15), (30, 25), (21, 38), (14, 55), (7, 75), (3, 88), (0, 98)]
    ]
    total_ceiling_cents: int = Field(default=50000, ge=0, le=50000)
    meta_ceiling_cents: int = Field(default=30000, ge=0, le=50000)
    google_ceiling_cents: int = Field(default=12500, ge=0, le=50000)
    reserve_cents: int = Field(default=7500, ge=0, le=50000)
    meta_test_cents: int = Field(default=7000, ge=0, le=30000)
    google_test_cents: int = Field(default=3000, ge=0, le=12500)
    watch_ratio: float = Field(default=0.8, gt=0, lt=1)
    near_full_tickets: int = Field(default=95, ge=1, le=109)
    watch_daily_cents: int = Field(default=800, ge=0, le=2500)
    action_daily_cents: int = Field(default=2000, ge=1500, le=2500)
    campaign_days: int = Field(default=3, ge=1, le=7)
    stale_after_hours: int = Field(default=48, ge=1, le=168)
    paid_window_days: int = Field(default=30, ge=1, le=60)
    # Launch economics and scenario defaults. Monetary values are integer cents;
    # revenue share is basis points (10,000 = 100%). Unknown economics remain nullable.
    baseline_ticket_price_cents: int = Field(default=650, ge=1, le=100000)
    attendance_target_pct: float = Field(default=80.0, ge=0, le=100)
    price_elasticity: float = Field(default=-1.0, ge=-5.0, le=-0.01)
    price_elasticity_uncertainty: float = Field(default=0.6, ge=0, le=3.0)
    revenue_share_bps: int | None = Field(default=None, ge=0, le=10000)
    fixed_cost_cents: int | None = Field(default=None, ge=0, le=100000000)
    variable_cost_per_ticket_cents: int | None = Field(default=None, ge=0, le=1000000)
    ad_incremental_cpa_cents: int | None = Field(default=None, ge=1, le=10000000)
    cannibalization_pct: float | None = Field(default=None, ge=0, le=100)
    sales_open_target: date = date(2026, 11, 16)
    paid_test_start: date = date(2027, 1, 4)
    paid_test_end: date = date(2027, 1, 10)

    @model_validator(mode="after")
    def coherent(self):
        if (
            self.meta_ceiling_cents + self.google_ceiling_cents + self.reserve_cents
            > self.total_ceiling_cents
        ):
            raise ValueError("Channel ceilings plus protected reserve exceed the total ceiling")
        if (
            self.meta_test_cents > self.meta_ceiling_cents
            or self.google_test_cents > self.google_ceiling_cents
        ):
            raise ValueError("Initial tests exceed channel ceilings")
        points = sorted(self.curve, key=lambda x: x.days)
        if len(points) < 2 or points[0].days != 0 or len({p.days for p in points}) != len(points):
            raise ValueError("Curve requires unique day values and a show-day target")
        if any(a.tickets < b.tickets for a, b in zip(points, points[1:])):
            raise ValueError("Targets must increase as the screening approaches")
        if self.paid_test_end < self.paid_test_start:
            raise ValueError("Test end precedes start")
        return self


class RuleUpdate(StrictModel):
    revision: int = Field(ge=1)
    rules: Rules


class ScenarioInput(StrictModel):
    screening_ids: list[str] | None = None
    ticket_price_cents: int | None = Field(default=None, ge=1, le=100000)
    advertising_budget_cents: int = Field(default=0, ge=0, le=100000000)
    attendance_target_pct: float | None = Field(default=None, ge=0, le=100)
    revenue_share_bps: int | None = Field(default=None, ge=0, le=10000)
    fixed_cost_cents: int | None = Field(default=None, ge=0, le=100000000)
    variable_cost_per_ticket_cents: int | None = Field(default=None, ge=0, le=1000000)
    price_elasticity: float | None = Field(default=None, ge=-5.0, le=-0.01)
    ad_incremental_cpa_cents: int | None = Field(default=None, ge=1, le=10000000)
    cannibalization_pct: float | None = Field(default=None, ge=0, le=100)

    @field_validator("screening_ids")
    @classmethod
    def unique_screenings(cls, value):
        if value is not None and not value:
            raise ValueError("Select at least one screening")
        if value is not None and len(value) != len(set(value)):
            raise ValueError("Screening selection contains duplicates")
        return value


class SnapshotInput(StrictModel):
    screening_id: str
    observed_at: datetime
    tickets_sold: int = Field(ge=0)
    note: str = Field(default="", max_length=1000)

    @field_validator("observed_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("Observation timestamp must include a timezone")
        if value > datetime.now(timezone.utc):
            raise ValueError("Future observations are not allowed")
        return value


class ScreeningUpdate(StrictModel):
    capacity: int | None = Field(default=None, ge=1, le=10000)
    capacity_confirmed: bool | None = None
    ticket_price_cents: int | None = Field(default=None, ge=1, le=1000000)
    time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    booking_url: HttpUrl | None = None
    sales_open_date: date | None = None
    sales_open_confirmed: bool = False

    @field_validator("booking_url")
    @classmethod
    def safe_link(cls, value):
        if value and value.scheme != "https":
            raise ValueError("Booking links must use HTTPS")
        return value


class CampaignInput(StrictModel):
    name: str = Field(min_length=2, max_length=150)
    platform: Literal["META", "GOOGLE"]
    ad_set: str = Field(default="", max_length=150)
    geography_id: str
    audience: str = Field(default="Adults 20–60 · local culture and music", max_length=250)
    creative_id: str
    screening_id: str
    start_date: date
    end_date: date
    budget_cents: int = Field(ge=0, le=50000)
    external_id: str | None = Field(default=None, max_length=150)

    @model_validator(mode="after")
    def dates(self):
        if self.end_date < self.start_date:
            raise ValueError("End date precedes start date")
        return self


class CreativeInput(StrictModel):
    name: str = Field(min_length=2, max_length=150)
    concept: str = Field(min_length=2, max_length=100)
    headline: str = Field(min_length=2, max_length=250)
    body: str = Field(min_length=2, max_length=2000)
    asset_url: HttpUrl | None = None
    status: Literal["DRAFT", "READY", "RETIRED"] = "DRAFT"

    @field_validator("asset_url")
    @classmethod
    def safe_asset(cls, value):
        if value and value.scheme != "https":
            raise ValueError("Asset links must use HTTPS")
        return value


class CampaignStatus(StrictModel):
    status: Literal["PLANNED", "ACTIVE", "PAUSED", "COMPLETED", "CANCELLED"]


class MetricInput(StrictModel):
    date: date
    spend_cents: int = Field(ge=0, le=10000000)
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    landing_page_views: int | None = Field(default=None, ge=0)
    attributed_tickets: int | None = Field(default=None, ge=0)
    attribution_note: str = Field(default="Platform attributed; not incremental sales.", max_length=1000)

    @model_validator(mode="after")
    def valid(self):
        if self.date > date.today():
            raise ValueError("Future campaign metrics are not allowed")
        if self.clicks > self.impressions:
            raise ValueError("Clicks cannot exceed impressions in this daily export")
        return self
