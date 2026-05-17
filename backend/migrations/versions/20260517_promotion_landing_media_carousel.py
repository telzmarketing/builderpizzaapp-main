"""promotion landing media carousel

Revision ID: 20260517_promotion_landing_media_carousel
Revises: 20260517_promotion_landing_pages
Create Date: 2026-05-17
"""

from alembic import op


revision = "20260517_promotion_landing_media_carousel"
down_revision = "20260517_promotion_landing_pages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE promotion_landing_pages ADD COLUMN IF NOT EXISTS image_url_2 TEXT")
    op.execute("ALTER TABLE promotion_landing_pages ADD COLUMN IF NOT EXISTS video_url TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE promotion_landing_pages DROP COLUMN IF EXISTS video_url")
    op.execute("ALTER TABLE promotion_landing_pages DROP COLUMN IF EXISTS image_url_2")
