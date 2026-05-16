"""store notification clear after view

Revision ID: 20260516_store_notification_clear_after_view
Revises: 20260515_pay_on_delivery, 20260515_product_promotion_benefits
Create Date: 2026-05-16
"""

from alembic import op


revision = "20260516_store_notification_clear_after_view"
down_revision = ("20260515_pay_on_delivery", "20260515_product_promotion_benefits")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE store_notifications "
        "ADD COLUMN IF NOT EXISTS clear_after_view BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE store_notifications DROP COLUMN IF EXISTS clear_after_view")
