"""Add provider media fields to WhatsApp templates.

Revision ID: 20260507_whatsapp_template_media
Revises: 20260507_whatsapp_providers_media
Create Date: 2026-05-07
"""

from alembic import op


revision = "20260507_whatsapp_template_media"
down_revision = "20260507_whatsapp_providers_media"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE whatsapp_templates ADD COLUMN IF NOT EXISTS provider VARCHAR(30) DEFAULT 'official'")
    op.execute("ALTER TABLE whatsapp_templates ADD COLUMN IF NOT EXISTS media_type VARCHAR(20)")
    op.execute("ALTER TABLE whatsapp_templates ADD COLUMN IF NOT EXISTS media_url TEXT")
    op.execute("ALTER TABLE whatsapp_templates ADD COLUMN IF NOT EXISTS caption TEXT")
    op.execute("ALTER TABLE whatsapp_templates ADD COLUMN IF NOT EXISTS mimetype VARCHAR(120)")
    op.execute("ALTER TABLE whatsapp_templates ADD COLUMN IF NOT EXISTS file_name VARCHAR(255)")


def downgrade() -> None:
    op.execute("ALTER TABLE whatsapp_templates DROP COLUMN IF EXISTS file_name")
    op.execute("ALTER TABLE whatsapp_templates DROP COLUMN IF EXISTS mimetype")
    op.execute("ALTER TABLE whatsapp_templates DROP COLUMN IF EXISTS caption")
    op.execute("ALTER TABLE whatsapp_templates DROP COLUMN IF EXISTS media_url")
    op.execute("ALTER TABLE whatsapp_templates DROP COLUMN IF EXISTS media_type")
    op.execute("ALTER TABLE whatsapp_templates DROP COLUMN IF EXISTS provider")
