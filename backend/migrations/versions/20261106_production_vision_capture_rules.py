"""Add tenant-scoped three-milestone Production Vision capture rules."""

from alembic import op
import sqlalchemy as sa


revision = "20261106_production_vision_capture_rules"
down_revision = "20261105_production_vision_station_crud"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_vision_capture_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("station_id", sa.String(80), nullable=False),
        sa.Column("milestone_1_name", sa.String(80), nullable=False, server_default="inicio"),
        sa.Column("milestone_1_seconds", sa.Integer, nullable=False, server_default="0"),
        sa.Column("milestone_2_name", sa.String(80), nullable=False, server_default="meio"),
        sa.Column("milestone_2_seconds", sa.Integer, nullable=False, server_default="30"),
        sa.Column("milestone_3_name", sa.String(80), nullable=False, server_default="fim"),
        sa.Column("milestone_3_seconds", sa.Integer, nullable=False, server_default="60"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("milestone_1_seconds >= 0 AND milestone_2_seconds >= 0 AND milestone_3_seconds >= 0", name="ck_production_vision_capture_seconds"),
    )
    op.create_index("uq_production_vision_capture_config_tenant_station", "production_vision_capture_configs", ["tenant_id", "station_id"], unique=True)

    op.create_table(
        "production_vision_capture_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("order_id", sa.String, nullable=False),
        sa.Column("production_unit_id", sa.String, nullable=False),
        sa.Column("station_id", sa.String(80), nullable=False),
        sa.Column("milestone", sa.String(40), nullable=False),
        sa.Column("mode", sa.String(12), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("photo_id", sa.String(36), sa.ForeignKey("production_vision_photos.id", ondelete="SET NULL")),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        sa.Column("reason", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id", "session_id"], ["production_vision_sessions.tenant_id", "production_vision_sessions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "order_id"], ["orders.tenant_id", "orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "production_unit_id"], ["production_units.tenant_id", "production_units.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("mode IN ('automatic','manual')", name="ck_production_vision_capture_mode"),
        sa.CheckConstraint("status IN ('pending','captured','unsupported')", name="ck_production_vision_capture_status"),
    )
    op.create_index("uq_production_vision_capture_event_tenant_idempotency", "production_vision_capture_events", ["tenant_id", "idempotency_key"], unique=True)
    op.create_index("uq_production_vision_capture_event_tenant_session_milestone", "production_vision_capture_events", ["tenant_id", "session_id", "milestone"], unique=True)
    op.create_index("ix_production_vision_capture_events_tenant_order", "production_vision_capture_events", ["tenant_id", "order_id"])


def downgrade() -> None:
    op.drop_index("ix_production_vision_capture_events_tenant_order", table_name="production_vision_capture_events")
    op.drop_index("uq_production_vision_capture_event_tenant_session_milestone", table_name="production_vision_capture_events")
    op.drop_index("uq_production_vision_capture_event_tenant_idempotency", table_name="production_vision_capture_events")
    op.drop_table("production_vision_capture_events")
    op.drop_index("uq_production_vision_capture_config_tenant_station", table_name="production_vision_capture_configs")
    op.drop_table("production_vision_capture_configs")
