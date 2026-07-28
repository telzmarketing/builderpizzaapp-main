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
        """
        CREATE TABLE IF NOT EXISTS email_templates (
            id VARCHAR PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            subject VARCHAR(500) NOT NULL,
            body_html TEXT NOT NULL,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS email_campaigns (
            id VARCHAR PRIMARY KEY,
            name VARCHAR(300) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'draft',
            template_id VARCHAR REFERENCES email_templates(id) ON DELETE SET NULL,
            group_id VARCHAR,
            scheduled_at TIMESTAMPTZ,
            sent_count INTEGER DEFAULT 0,
            delivered_count INTEGER DEFAULT 0,
            open_count INTEGER DEFAULT 0,
            click_count INTEGER DEFAULT 0,
            bounce_count INTEGER DEFAULT 0,
            unsubscribe_count INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_email_campaigns_status "
        "ON email_campaigns(status)"
    )
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
