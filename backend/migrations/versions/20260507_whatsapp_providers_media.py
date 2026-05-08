"""Add WhatsApp provider and media fields.

Revision ID: 20260507_whatsapp_providers_media
Revises: 20260507_notification_captured
Create Date: 2026-05-07
"""

from alembic import op


revision = "20260507_whatsapp_providers_media"
down_revision = "20260507_notification_captured"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS provider VARCHAR(30) DEFAULT 'official'")
    op.execute("ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS message_type VARCHAR(30) DEFAULT 'text'")
    op.execute("ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS media_type VARCHAR(20)")
    op.execute("ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS media_url TEXT")
    op.execute("ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS caption TEXT")
    op.execute("ALTER TABLE whatsapp_config ADD COLUMN IF NOT EXISTS evolution_base_url VARCHAR(500) DEFAULT ''")
    op.execute("ALTER TABLE whatsapp_config ADD COLUMN IF NOT EXISTS evolution_api_key TEXT DEFAULT ''")
    op.execute("ALTER TABLE whatsapp_config ADD COLUMN IF NOT EXISTS evolution_instance VARCHAR(120) DEFAULT ''")


def downgrade() -> None:
    op.execute("ALTER TABLE whatsapp_config DROP COLUMN IF EXISTS evolution_instance")
    op.execute("ALTER TABLE whatsapp_config DROP COLUMN IF EXISTS evolution_api_key")
    op.execute("ALTER TABLE whatsapp_config DROP COLUMN IF EXISTS evolution_base_url")
    op.execute("ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS caption")
    op.execute("ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS media_url")
    op.execute("ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS media_type")
    op.execute("ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS message_type")
    op.execute("ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS provider")
