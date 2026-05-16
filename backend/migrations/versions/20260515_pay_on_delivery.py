"""pay on delivery payment details

Revision ID: 20260515_pay_on_delivery
Revises: 20260515_visitor_neighborhood_bi
Create Date: 2026-05-15
"""

from alembic import op


revision = "20260515_pay_on_delivery"
down_revision = "20260515_visitor_neighborhood_bi"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS pay_on_delivery BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS delivery_payment_method VARCHAR(20)")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS cash_needs_change BOOLEAN")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS cash_change_for DOUBLE PRECISION")
    op.execute("UPDATE payment_gateway_config SET accept_cash = TRUE WHERE id = 'default'")


def downgrade() -> None:
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS cash_change_for")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS cash_needs_change")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS delivery_payment_method")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS pay_on_delivery")
