"""Initial REEF Launch Intelligence schema."""

from alembic import op
from reef import models  # noqa: F401 - registers all migration tables
from reef.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Freeze the original migration boundary. Using every table currently registered
# in Base.metadata would make old migrations silently create tables introduced by
# later revisions (for example traffic_metrics from 0002) on a fresh database.
INITIAL_TABLE_NAMES = {
    "projects",
    "screenings",
    "ticket_snapshots",
    "historical_snapshots",
    "geographies",
    "creatives",
    "campaigns",
    "campaign_metrics",
    "audit_events",
    "user_accounts",
    "login_sessions",
    "login_attempts",
}


def _initial_tables():
    return [table for table in Base.metadata.sorted_tables if table.name in INITIAL_TABLE_NAMES]


def upgrade():
    Base.metadata.create_all(op.get_bind(), tables=_initial_tables())


def downgrade():
    Base.metadata.drop_all(op.get_bind(), tables=_initial_tables())
