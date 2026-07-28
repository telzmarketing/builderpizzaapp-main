"""whatsapp uazapi unofficial provider

Revision ID: 20260527_whatsapp_uazapi_unofficial
Revises: 20260527_delivery_person_deleted_at
Create Date: 2026-05-27
"""
from __future__ import annotations

from alembic import op


revision = "20260527_whatsapp_uazapi_unofficial"
down_revision = "20260527_delivery_person_deleted_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS integration_connections (
            id VARCHAR PRIMARY KEY,
            integration_type VARCHAR(50) NOT NULL,
            status VARCHAR(20) DEFAULT 'disconnected',
            credentials_json TEXT,
            last_sync_at TIMESTAMPTZ,
            last_error TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_integration_type UNIQUE(integration_type)
        )
        """
    )
    op.execute(
        """
        INSERT INTO integration_connections (id, integration_type)
        VALUES
            ('meta_ads', 'meta_ads'),
            ('google_ads', 'google_ads'),
            ('tiktok_ads', 'tiktok_ads'),
            ('whatsapp_cloud', 'whatsapp_cloud'),
            ('whatsapp_qr', 'whatsapp_qr'),
            ('smtp', 'smtp')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute("ALTER TABLE whatsapp_config ADD COLUMN IF NOT EXISTS uazapi_base_url VARCHAR(500) DEFAULT ''")
    op.execute("ALTER TABLE whatsapp_config ADD COLUMN IF NOT EXISTS uazapi_token TEXT DEFAULT ''")
    op.execute("ALTER TABLE whatsapp_config ADD COLUMN IF NOT EXISTS uazapi_instance VARCHAR(120) DEFAULT ''")
    op.execute(
        """
        INSERT INTO integration_connections (id, integration_type)
        VALUES ('whatsapp_unofficial', 'whatsapp_unofficial')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM integration_connections WHERE integration_type = 'whatsapp_unofficial'")
    op.execute("ALTER TABLE whatsapp_config DROP COLUMN IF EXISTS uazapi_instance")
    op.execute("ALTER TABLE whatsapp_config DROP COLUMN IF EXISTS uazapi_token")
    op.execute("ALTER TABLE whatsapp_config DROP COLUMN IF EXISTS uazapi_base_url")
