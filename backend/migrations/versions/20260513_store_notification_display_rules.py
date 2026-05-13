"""store notification display rules

Revision ID: 20260513_store_notification_display_rules
Revises: 20260512_exit_popup_delay
Create Date: 2026-05-13
"""

from alembic import op


revision = "20260513_store_notification_display_rules"
down_revision = "20260512_exit_popup_delay"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE store_notifications "
        "ADD COLUMN IF NOT EXISTS purchase_minutes_ago INTEGER NOT NULL DEFAULT 12"
    )
    op.execute(
        "ALTER TABLE store_notification_impressions "
        "ADD COLUMN IF NOT EXISTS customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE store_notification_impressions "
        "ADD COLUMN IF NOT EXISTS anonymous_session_id VARCHAR(120)"
    )
    op.execute(
        "ALTER TABLE store_notification_impressions "
        "ADD COLUMN IF NOT EXISTS notification_type VARCHAR(20)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_store_notification_impressions_customer_id "
        "ON store_notification_impressions(customer_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_store_notification_impressions_anonymous_session_id "
        "ON store_notification_impressions(anonymous_session_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_store_notification_impressions_identity_notification "
        "ON store_notification_impressions(notification_id, customer_id, anonymous_session_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_store_notification_impressions_identity_notification")
    op.execute("DROP INDEX IF EXISTS ix_store_notification_impressions_anonymous_session_id")
    op.execute("DROP INDEX IF EXISTS ix_store_notification_impressions_customer_id")
    op.execute("ALTER TABLE store_notification_impressions DROP COLUMN IF EXISTS notification_type")
    op.execute("ALTER TABLE store_notification_impressions DROP COLUMN IF EXISTS anonymous_session_id")
    op.execute("ALTER TABLE store_notification_impressions DROP COLUMN IF EXISTS customer_id")
    op.execute("ALTER TABLE store_notifications DROP COLUMN IF EXISTS purchase_minutes_ago")
