"""Add email contact lists.

Revision ID: 20260704_email_contact_lists
Revises: 20260703_asaas_card_metadata
Create Date: 2026-07-04
"""

from alembic import op


revision = "20260704_email_contact_lists"
down_revision = "20260703_asaas_card_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS email_contact_lists (
            id VARCHAR PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_email_contact_lists_active ON email_contact_lists(active)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS email_contact_list_items (
            id VARCHAR PRIMARY KEY,
            list_id VARCHAR NOT NULL REFERENCES email_contact_lists(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            email VARCHAR(300) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_email_contact_list_items_list_id ON email_contact_list_items(list_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_email_contact_list_items_email ON email_contact_list_items(email)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS email_contact_list_items")
    op.execute("DROP TABLE IF EXISTS email_contact_lists")
