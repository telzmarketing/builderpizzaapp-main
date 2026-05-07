"""store notifications social proof module

Revision ID: 20260506_store_notifications
Revises: 20260506_campaign_product_link
Create Date: 2026-05-06
"""

from alembic import op

revision = "20260506_store_notifications"
down_revision = "20260506_campaign_product_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS store_notification_settings (
            id VARCHAR PRIMARY KEY DEFAULT 'default',
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            real_orders_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            real_percentage INTEGER NOT NULL DEFAULT 70,
            manual_percentage INTEGER NOT NULL DEFAULT 30,
            min_delay_seconds INTEGER NOT NULL DEFAULT 45,
            max_delay_seconds INTEGER NOT NULL DEFAULT 120,
            default_display_seconds INTEGER NOT NULL DEFAULT 7,
            prevent_same_product_sequence BOOLEAN NOT NULL DEFAULT TRUE,
            prevent_same_neighborhood_sequence BOOLEAN NOT NULL DEFAULT FALSE,
            only_during_store_hours BOOLEAN NOT NULL DEFAULT FALSE,
            allowed_pages TEXT NOT NULL DEFAULT '["home", "cardapio", "product", "cart"]',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("INSERT INTO store_notification_settings (id) VALUES ('default') ON CONFLICT DO NOTHING")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS store_notifications (
            id VARCHAR PRIMARY KEY,
            type VARCHAR(20) NOT NULL DEFAULT 'manual',
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            internal_name VARCHAR(200) NOT NULL,
            display_name VARCHAR(120) NOT NULL,
            product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL,
            neighborhood VARCHAR(120),
            template_text TEXT NOT NULL,
            priority VARCHAR(20) NOT NULL DEFAULT 'medium',
            weight INTEGER NOT NULL DEFAULT 1,
            display_seconds INTEGER NOT NULL DEFAULT 7,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            start_date DATE,
            end_date DATE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS store_notification_days (
            id VARCHAR PRIMARY KEY,
            notification_id VARCHAR NOT NULL REFERENCES store_notifications(id) ON DELETE CASCADE,
            weekday INTEGER NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS store_notification_impressions (
            id VARCHAR PRIMARY KEY,
            notification_id VARCHAR REFERENCES store_notifications(id) ON DELETE SET NULL,
            source_type VARCHAR(20) NOT NULL,
            order_id VARCHAR REFERENCES orders(id) ON DELETE SET NULL,
            product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL,
            neighborhood VARCHAR(120),
            page VARCHAR(40),
            displayed_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_notification_days_notification_id ON store_notification_days(notification_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_notification_days_weekday ON store_notification_days(weekday)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_notification_impressions_notification_id ON store_notification_impressions(notification_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_notification_impressions_order_id ON store_notification_impressions(order_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_notification_impressions_product_id ON store_notification_impressions(product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_notification_impressions_page ON store_notification_impressions(page)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_notification_impressions_displayed_at ON store_notification_impressions(displayed_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS store_notification_impressions")
    op.execute("DROP TABLE IF EXISTS store_notification_days")
    op.execute("DROP TABLE IF EXISTS store_notifications")
    op.execute("DROP TABLE IF EXISTS store_notification_settings")
