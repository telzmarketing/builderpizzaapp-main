"""Add WhatsApp contact lists.

Revision ID: 20260508_whatsapp_contact_lists
Revises: 20260507_whatsapp_interval_range
Create Date: 2026-05-08
"""

from alembic import op


revision = "20260508_whatsapp_contact_lists"
down_revision = "20260507_whatsapp_interval_range"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_contact_lists (
            id VARCHAR PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_contact_lists_active ON whatsapp_contact_lists(active)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_contact_list_items (
            id VARCHAR PRIMARY KEY,
            list_id VARCHAR NOT NULL REFERENCES whatsapp_contact_lists(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            phone VARCHAR(20) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_contact_list_items_list_id ON whatsapp_contact_list_items(list_id)")
    op.execute("ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS recipient_name VARCHAR(200)")


def downgrade() -> None:
    op.execute("ALTER TABLE whatsapp_messages DROP COLUMN IF EXISTS recipient_name")
    op.execute("DROP TABLE IF EXISTS whatsapp_contact_list_items")
    op.execute("DROP TABLE IF EXISTS whatsapp_contact_lists")
