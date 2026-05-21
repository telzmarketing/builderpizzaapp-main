"""Add salao blog posts settings.

Revision ID: 20260520_salao_blog_posts
Revises: 20260520_promotion_landing_label_accents
Create Date: 2026-05-20 20:20:00.000000
"""

from alembic import op


revision = "20260520_salao_blog_posts"
down_revision = "20260520_promotion_landing_label_accents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE salao_page_settings ADD COLUMN IF NOT EXISTS blog_posts_json TEXT NOT NULL DEFAULT '[]'")


def downgrade() -> None:
    op.execute("ALTER TABLE salao_page_settings DROP COLUMN IF EXISTS blog_posts_json")
