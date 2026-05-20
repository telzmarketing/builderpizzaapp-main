"""Add original site CMS override fields

Revision ID: 20260520_salao_site_cms_overrides
Revises: 20260520_salao_page_settings
Create Date: 2026-05-20
"""

from alembic import op


revision = "20260520_salao_site_cms_overrides"
down_revision = "20260520_salao_page_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE salao_page_settings ADD COLUMN IF NOT EXISTS site_text_overrides_json TEXT NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE salao_page_settings ADD COLUMN IF NOT EXISTS site_image_overrides_json TEXT NOT NULL DEFAULT '{}'")


def downgrade() -> None:
    op.execute("ALTER TABLE salao_page_settings DROP COLUMN IF EXISTS site_image_overrides_json")
    op.execute("ALTER TABLE salao_page_settings DROP COLUMN IF EXISTS site_text_overrides_json")
