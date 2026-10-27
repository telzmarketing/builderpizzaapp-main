"""Persist per-unit KDS dispatch completion."""

from alembic import op
import sqlalchemy as sa


revision = "20261027_kds_dispatch_unit_completion"
down_revision = "20261026_order_driver_delivery_fee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "production_units",
        sa.Column("dispatch_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "production_units",
        sa.Column("dispatch_completed_by", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_production_units_dispatch_completed_by_admin_users",
        "production_units",
        "admin_users",
        ["dispatch_completed_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_production_units_dispatch_completion",
        "production_units",
        ["tenant_id", "order_id", "dispatch_completed_at"],
    )


def downgrade() -> None:
    raise RuntimeError("Forward-only: preserve per-unit dispatch history.")
