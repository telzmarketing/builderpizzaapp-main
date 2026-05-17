"""promotion landing pages

Revision ID: 20260517_promotion_landing_pages
Revises: 20260516_store_notification_clear_after_view
Create Date: 2026-05-17
"""

from alembic import op


revision = "20260517_promotion_landing_pages"
down_revision = "20260516_store_notification_clear_after_view"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS promotion_landing_pages (
            id VARCHAR PRIMARY KEY,
            product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            promotion_id VARCHAR NOT NULL REFERENCES product_promotions(id) ON DELETE CASCADE,
            title VARCHAR(220) NOT NULL,
            subtitle VARCHAR(500),
            description TEXT,
            cta_text VARCHAR(80) NOT NULL DEFAULT 'Quero essa pizza',
            image_url TEXT,
            image_position VARCHAR(40) NOT NULL DEFAULT 'center',
            content_alignment VARCHAR(20) NOT NULL DEFAULT 'center',
            overlay_style VARCHAR(40) NOT NULL DEFAULT 'dark-gradient',
            badge_text VARCHAR(80),
            slug VARCHAR(160) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            published_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_promotion_landing_pages_slug ON promotion_landing_pages(slug)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_promotion_landing_pages_product_id ON promotion_landing_pages(product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_promotion_landing_pages_promotion_id ON promotion_landing_pages(promotion_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_promotion_landing_pages_status ON promotion_landing_pages(status)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS promotion_landing_pages")
