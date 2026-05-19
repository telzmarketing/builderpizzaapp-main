"""Add media order to promotion landing pages.

Revision ID: 20260519_promotion_landing_media_order
Revises: 20260517_promotion_landing_media_carousel
Create Date: 2026-05-19
"""

from alembic import op


revision = "20260519_promotion_landing_media_order"
down_revision = "20260517_promotion_landing_media_carousel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE promotion_landing_pages "
        "ADD COLUMN IF NOT EXISTS media_order JSONB NOT NULL "
        "DEFAULT '[\"image_url\", \"image_url_2\", \"video_url\"]'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE promotion_landing_pages DROP COLUMN IF EXISTS media_order")
