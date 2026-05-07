"""notification captured queue e initial delay

Revision ID: 20260507_notification_captured
Revises: 20260506_store_notifications
Create Date: 2026-05-07
"""

from alembic import op

revision = "20260507_notification_captured"
down_revision = "20260506_store_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE store_notification_settings "
        "ADD COLUMN IF NOT EXISTS initial_delay_seconds INTEGER NOT NULL DEFAULT 5"
    )
    op.execute(
        "ALTER TABLE store_notifications "
        "ADD COLUMN IF NOT EXISTS source_customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS store_notification_captured (
            id VARCHAR PRIMARY KEY,
            order_id VARCHAR REFERENCES orders(id) ON DELETE CASCADE,
            customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
            product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL,
            product_name VARCHAR(200),
            product_image VARCHAR(500),
            neighborhood VARCHAR(120),
            buyer_name VARCHAR(120),
            order_time TIMESTAMPTZ,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_snc_order_id "
        "ON store_notification_captured(order_id) WHERE order_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_snc_status ON store_notification_captured(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_snc_created_at ON store_notification_captured(created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS store_notification_captured")
    op.execute(
        "ALTER TABLE store_notifications DROP COLUMN IF EXISTS source_customer_id"
    )
    op.execute(
        "ALTER TABLE store_notification_settings DROP COLUMN IF EXISTS initial_delay_seconds"
    )
