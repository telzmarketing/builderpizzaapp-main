"""Add a durable retry queue for failed finance projections."""

from alembic import op
import sqlalchemy as sa


revision = "20261124_finance_projection_queue"
down_revision = "20261124_finance_operational_enablement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_projection_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("event_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("aggregate_type", sa.String(80), nullable=True),
        sa.Column("aggregate_id", sa.String(160), nullable=True),
        sa.Column("source_type", sa.String(80), nullable=True),
        sa.Column("source_id", sa.String(160), nullable=True),
        sa.Column("payload_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("dedupe_key", sa.String(240), nullable=False),
        sa.Column("correlation_id", sa.String(160), nullable=True),
        sa.Column("causation_id", sa.String(160), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="5"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(160), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "dedupe_key", name="uq_finance_projection_events_tenant_dedupe"),
        sa.CheckConstraint("status IN ('pending','processing','processed','failed','dead')", name="ck_finance_projection_events_status"),
        sa.CheckConstraint("attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts", name="ck_finance_projection_events_attempts"),
    )
    op.create_index(
        "ix_finance_projection_events_claim",
        "finance_projection_events",
        ["tenant_id", "status", "available_at", "created_at"],
    )
    op.create_index(
        "ix_finance_projection_events_aggregate",
        "finance_projection_events",
        ["tenant_id", "aggregate_type", "aggregate_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_finance_projection_events_aggregate", table_name="finance_projection_events")
    op.drop_index("ix_finance_projection_events_claim", table_name="finance_projection_events")
    op.drop_table("finance_projection_events")
