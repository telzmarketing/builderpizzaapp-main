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
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_templates (
            id VARCHAR PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            body TEXT NOT NULL,
            category VARCHAR(50) DEFAULT 'marketing',
            language VARCHAR(10) DEFAULT 'pt_BR',
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_messages (
            id VARCHAR PRIMARY KEY,
            template_id VARCHAR REFERENCES whatsapp_templates(id) ON DELETE SET NULL,
            customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
            phone VARCHAR(20) NOT NULL,
            body_sent TEXT,
            status VARCHAR(20) DEFAULT 'pending',
            wamid VARCHAR(200),
            error TEXT,
            sent_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_config (
            id VARCHAR PRIMARY KEY DEFAULT 'default',
            connection_type VARCHAR(30) DEFAULT 'official',
            status VARCHAR(20) DEFAULT 'disconnected',
            messages_per_minute INTEGER DEFAULT 10,
            interval_seconds INTEGER DEFAULT 3,
            daily_limit INTEGER DEFAULT 1000,
            webhook_url VARCHAR(500) DEFAULT '',
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("INSERT INTO whatsapp_config (id) VALUES ('default') ON CONFLICT DO NOTHING")

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
