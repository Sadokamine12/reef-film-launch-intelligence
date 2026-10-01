"""Add location-level website traffic evidence."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "traffic_metrics",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=50), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("geography_id", sa.String(length=30), sa.ForeignKey("geographies.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sessions", sa.Integer(), nullable=False),
        sa.Column("ticket_clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="MANUAL"),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sessions >= 0 AND ticket_clicks >= 0"),
        sa.UniqueConstraint("project_id", "geography_id", "date", "source"),
    )
    op.create_index("ix_traffic_metrics_project_id", "traffic_metrics", ["project_id"])
    op.create_index("ix_traffic_metrics_geography_id", "traffic_metrics", ["geography_id"])
    op.create_index("ix_traffic_metrics_date", "traffic_metrics", ["date"])


def downgrade():
    op.drop_index("ix_traffic_metrics_date", table_name="traffic_metrics")
    op.drop_index("ix_traffic_metrics_geography_id", table_name="traffic_metrics")
    op.drop_index("ix_traffic_metrics_project_id", table_name="traffic_metrics")
    op.drop_table("traffic_metrics")
