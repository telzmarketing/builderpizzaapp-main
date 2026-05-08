"""Add random interval range to WhatsApp config.

Revision ID: 20260507_whatsapp_interval_range
Revises: 20260507_whatsapp_template_media
Create Date: 2026-05-07
"""

from alembic import op


revision = "20260507_whatsapp_interval_range"
down_revision = "20260507_whatsapp_template_media"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE whatsapp_config ADD COLUMN IF NOT EXISTS interval_min_seconds INTEGER DEFAULT 3")
    op.execute("ALTER TABLE whatsapp_config ADD COLUMN IF NOT EXISTS interval_max_seconds INTEGER DEFAULT 8")
    op.execute(
        """
        UPDATE whatsapp_config
        SET interval_min_seconds = COALESCE(interval_min_seconds, interval_seconds, 3),
            interval_max_seconds = COALESCE(interval_max_seconds, interval_seconds, 8)
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE whatsapp_config DROP COLUMN IF EXISTS interval_max_seconds")
    op.execute("ALTER TABLE whatsapp_config DROP COLUMN IF EXISTS interval_min_seconds")
