"""Add tenant-scoped one-to-one KDS device/station bindings."""

from alembic import op
import sqlalchemy as sa


revision = "20261117_production_vision_devices"
down_revision = "20261117_order_app_finance_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_vision_devices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("identifier", sa.String(120), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("station_id", sa.String(80), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_production_vision_device_status"),
    )
    op.create_index("uq_production_vision_devices_tenant_identifier", "production_vision_devices", ["tenant_id", "identifier"], unique=True)
    op.create_index("uq_production_vision_devices_tenant_station", "production_vision_devices", ["tenant_id", "station_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_production_vision_devices_tenant_station", table_name="production_vision_devices")
    op.drop_index("uq_production_vision_devices_tenant_identifier", table_name="production_vision_devices")
    op.drop_table("production_vision_devices")
