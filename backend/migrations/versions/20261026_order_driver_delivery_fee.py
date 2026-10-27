"""Snapshot distance freight as the driver's delivery payout."""

from alembic import op
import sqlalchemy as sa


revision = "20261026_order_driver_delivery_fee"
down_revision = "20261026_product_crust_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("driver_delivery_fee", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "driver_delivery_fee")
