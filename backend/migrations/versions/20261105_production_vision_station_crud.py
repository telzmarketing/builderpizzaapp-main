"""Add tenant-scoped custom Production Vision stations."""

from alembic import op
import sqlalchemy as sa


revision = "20261105_production_vision_station_crud"
down_revision = "20261104_fixed_pizza_stations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_vision_stations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("identifier", sa.String(80), nullable=False),
        sa.Column("station_type", sa.String(12), nullable=False, server_default="custom"),
        sa.Column("status", sa.String(12), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("station_type IN ('custom')", name="ck_production_vision_station_type"),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_production_vision_station_status"),
    )
    op.create_index(
        "uq_production_vision_stations_tenant_identifier",
        "production_vision_stations",
        ["tenant_id", "identifier"],
        unique=True,
    )
    op.create_index("ix_production_vision_stations_tenant_status", "production_vision_stations", ["tenant_id", "status"])
    # Custom station identifiers can be up to 80 characters; existing
    # Production Vision columns were sized for the original short identifiers.
    for table in ("production_vision_cameras", "production_vision_zones"):
        op.alter_column(table, "station_id", existing_type=sa.String(length=20), type_=sa.String(length=80), existing_nullable=False)
    op.alter_column(
        "production_vision_sessions",
        "station_id",
        existing_type=sa.String(length=20),
        type_=sa.String(length=80),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Forward-only production policy: custom stations may already be referenced
    # by cameras, zones, or sessions, so an automatic downgrade is unsafe.
    pass
