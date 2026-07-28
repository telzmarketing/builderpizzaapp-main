"""visitor location fields

Revision ID: 20260511_visitor_location_status
Revises: 20260508_whatsapp_contact_lists
Create Date: 2026-05-11
"""

from alembic import op


revision = "20260511_visitor_location_status"
down_revision = "20260508_whatsapp_contact_lists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS visitor_profiles (
            id VARCHAR PRIMARY KEY,
            fingerprint VARCHAR(128) UNIQUE,
            customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
            ip_hash VARCHAR(64),
            city VARCHAR(100),
            state VARCHAR(50),
            country VARCHAR(50),
            device_type VARCHAR(30),
            browser VARCHAR(80),
            os VARCHAR(80),
            first_seen_at TIMESTAMPTZ DEFAULT NOW(),
            last_seen_at TIMESTAMPTZ DEFAULT NOW(),
            total_sessions INTEGER DEFAULT 0,
            total_pageviews INTEGER DEFAULT 0,
            total_orders INTEGER DEFAULT 0
        )
        """
    )

    op.execute("ALTER TABLE visitor_profiles ADD COLUMN IF NOT EXISTS latitude FLOAT")
    op.execute("ALTER TABLE visitor_profiles ADD COLUMN IF NOT EXISTS longitude FLOAT")
    op.execute("ALTER TABLE visitor_profiles ADD COLUMN IF NOT EXISTS location_accuracy_m FLOAT")
    op.execute("ALTER TABLE visitor_profiles ADD COLUMN IF NOT EXISTS location_captured_at TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE visitor_profiles DROP COLUMN IF EXISTS location_captured_at")
    op.execute("ALTER TABLE visitor_profiles DROP COLUMN IF EXISTS location_accuracy_m")
    op.execute("ALTER TABLE visitor_profiles DROP COLUMN IF EXISTS longitude")
    op.execute("ALTER TABLE visitor_profiles DROP COLUMN IF EXISTS latitude")
