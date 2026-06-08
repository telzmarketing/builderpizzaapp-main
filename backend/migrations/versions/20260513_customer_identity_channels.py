"""customer identity channels

Revision ID: 20260513_customer_identity_channels
Revises: 20260513_store_notification_display_rules
Create Date: 2026-05-13
"""
from __future__ import annotations

from alembic import op

revision = "20260513_customer_identity_channels"
down_revision = "20260513_store_notification_display_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_auth (
            id VARCHAR PRIMARY KEY,
            customer_id VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            auth_provider VARCHAR(40) NOT NULL DEFAULT 'password',
            identifier VARCHAR(255),
            password_hash TEXT,
            provider_subject VARCHAR(255),
            status VARCHAR(30) NOT NULL DEFAULT 'active',
            last_login_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_customer_auth_customer_provider UNIQUE (customer_id, auth_provider),
            CONSTRAINT uq_customer_auth_provider_identifier UNIQUE (auth_provider, identifier)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_auth_customer_id ON customer_auth(customer_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_channels (
            id VARCHAR PRIMARY KEY,
            customer_id VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            channel VARCHAR(40) NOT NULL,
            identifier VARCHAR(255) NOT NULL,
            normalized_identifier VARCHAR(255) NOT NULL,
            is_primary BOOLEAN NOT NULL DEFAULT FALSE,
            verified_at TIMESTAMPTZ,
            marketing_consent BOOLEAN NOT NULL DEFAULT FALSE,
            source VARCHAR(100),
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_customer_channel_identifier UNIQUE (channel, normalized_identifier)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_channels_customer_id ON customer_channels(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_channels_channel ON customer_channels(channel)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_preferences (
            id VARCHAR PRIMARY KEY,
            customer_id VARCHAR NOT NULL UNIQUE REFERENCES customers(id) ON DELETE CASCADE,
            preferred_channel VARCHAR(40),
            preferred_contact_time VARCHAR(40),
            language VARCHAR(10) NOT NULL DEFAULT 'pt_BR',
            accepts_ai_service BOOLEAN NOT NULL DEFAULT TRUE,
            accepts_order_status BOOLEAN NOT NULL DEFAULT TRUE,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        INSERT INTO customer_channels (
            id, customer_id, channel, identifier, normalized_identifier,
            is_primary, marketing_consent, source
        )
        SELECT
            'cchan-email-' || substr(md5(c.id || '-email'), 1, 20),
            c.id,
            'email',
            c.email,
            lower(c.email),
            CASE WHEN c.phone IS NULL OR c.phone = '' THEN TRUE ELSE FALSE END,
            COALESCE(c.marketing_email_consent, FALSE),
            COALESCE(c.source, 'legacy')
        FROM customers c
        WHERE c.email IS NOT NULL AND c.email <> ''
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO customer_channels (
            id, customer_id, channel, identifier, normalized_identifier,
            is_primary, marketing_consent, source
        )
        SELECT
            'cchan-phone-' || substr(md5(c.id || '-phone'), 1, 20),
            c.id,
            'phone',
            c.phone,
            regexp_replace(c.phone, '[^0-9]', '', 'g'),
            TRUE,
            COALESCE(c.marketing_whatsapp_consent, FALSE),
            COALESCE(c.source, 'legacy')
        FROM customers c
        WHERE c.phone IS NOT NULL
          AND c.phone <> ''
          AND regexp_replace(c.phone, '[^0-9]', '', 'g') <> ''
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO customer_channels (
            id, customer_id, channel, identifier, normalized_identifier,
            is_primary, marketing_consent, source
        )
        SELECT
            'cchan-wpp-' || substr(md5(c.id || '-whatsapp'), 1, 22),
            c.id,
            'whatsapp',
            c.phone,
            regexp_replace(c.phone, '[^0-9]', '', 'g'),
            TRUE,
            COALESCE(c.marketing_whatsapp_consent, FALSE),
            COALESCE(c.source, 'legacy')
        FROM customers c
        WHERE c.phone IS NOT NULL
          AND c.phone <> ''
          AND regexp_replace(c.phone, '[^0-9]', '', 'g') <> ''
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO customer_auth (
            id, customer_id, auth_provider, identifier, password_hash, status
        )
        SELECT
            'cauth-pass-' || substr(md5(c.id || '-password'), 1, 20),
            c.id,
            'password',
            lower(c.email),
            c.password_hash,
            CASE WHEN c.password_hash IS NULL THEN 'inactive' ELSE 'active' END
        FROM customers c
        WHERE c.email IS NOT NULL AND c.email <> ''
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO customer_preferences (id, customer_id, preferred_channel)
        SELECT
            'cpref-' || substr(md5(c.id || '-preferences'), 1, 26),
            c.id,
            CASE WHEN c.phone IS NOT NULL AND c.phone <> '' THEN 'whatsapp' ELSE 'email' END
        FROM customers c
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS customer_preferences")
    op.execute("DROP TABLE IF EXISTS customer_channels")
    op.execute("DROP TABLE IF EXISTS customer_auth")
