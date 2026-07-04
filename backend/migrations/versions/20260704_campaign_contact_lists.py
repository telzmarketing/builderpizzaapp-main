"""Add contact lists to marketing campaigns.

Revision ID: 20260704_campaign_contact_lists
Revises: 20260704_email_contact_lists
Create Date: 2026-07-04
"""

from alembic import op


revision = "20260704_campaign_contact_lists"
down_revision = "20260704_email_contact_lists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE whatsapp_campaigns "
        "ADD COLUMN IF NOT EXISTS contact_list_id VARCHAR "
        "REFERENCES whatsapp_contact_lists(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE email_campaigns "
        "ADD COLUMN IF NOT EXISTS contact_list_id VARCHAR "
        "REFERENCES email_contact_lists(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE email_campaigns DROP COLUMN IF EXISTS contact_list_id")
    op.execute("ALTER TABLE whatsapp_campaigns DROP COLUMN IF EXISTS contact_list_id")
