"""delivery radius and payment retry

Revision ID: 20260610_delivery_radius_and_payment_retry
Revises: 20260610_whatsapp_provider_consolidation
"""

from alembic import op

revision = "20260610_delivery_radius_and_payment_retry"
down_revision = "20260610_whatsapp_provider_consolidation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE shipping_config
        SET max_delivery_distance = 3.0
        WHERE id = 'default'
          AND (max_delivery_distance IS NULL OR max_delivery_distance > 3.0)
        """
    )


def downgrade() -> None:
    pass
