"""Initial REEF Launch Intelligence schema."""

from alembic import op
from reef import models  # noqa: F401 - registers all migration tables
from reef.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(op.get_bind())


def downgrade():
    Base.metadata.drop_all(op.get_bind())
