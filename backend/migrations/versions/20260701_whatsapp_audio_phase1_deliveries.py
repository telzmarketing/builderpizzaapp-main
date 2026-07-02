"""whatsapp audio phase1 deliveries

Revision ID: 20260701_whatsapp_audio_phase1_deliveries
Revises: 20260630_gestao_fiscal_sefaz_base
"""
from __future__ import annotations

from alembic import op

revision = "20260701_whatsapp_audio_phase1_deliveries"
down_revision = "20260630_gestao_fiscal_sefaz_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_campaign_deliveries (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            company_id VARCHAR(80) NOT NULL DEFAULT 'default',
            whatsapp_message_id VARCHAR REFERENCES whatsapp_messages(id) ON DELETE SET NULL,
            campaign_id VARCHAR REFERENCES whatsapp_campaigns(id) ON DELETE SET NULL,
            template_id VARCHAR REFERENCES whatsapp_templates(id) ON DELETE SET NULL,
            customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
            conversation_id VARCHAR REFERENCES agente_whatsapp_sessions(id) ON DELETE SET NULL,
            agente_message_id VARCHAR REFERENCES agente_whatsapp_messages(id) ON DELETE SET NULL,
            phone_normalized VARCHAR(30) NOT NULL,
            recipient_name VARCHAR(200),
            provider VARCHAR(40) NOT NULL DEFAULT 'official',
            provider_message_id VARCHAR(255),
            message_type VARCHAR(30) NOT NULL DEFAULT 'text',
            message_text_snapshot TEXT,
            media_type VARCHAR(20),
            media_url TEXT,
            caption_snapshot TEXT,
            template_name_snapshot VARCHAR(200),
            campaign_name_snapshot VARCHAR(300),
            variables_json TEXT NOT NULL DEFAULT '{}',
            provider_payload_json TEXT NOT NULL DEFAULT '{}',
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            sent_at TIMESTAMPTZ,
            delivered_at TIMESTAMPTZ,
            read_at TIMESTAMPTZ,
            replied_at TIMESTAMPTZ,
            failed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_campaign_deliveries_tenant_id ON whatsapp_campaign_deliveries(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_campaign_deliveries_company_id ON whatsapp_campaign_deliveries(company_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_campaign_deliveries_whatsapp_message_id ON whatsapp_campaign_deliveries(whatsapp_message_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_campaign_deliveries_campaign_id ON whatsapp_campaign_deliveries(campaign_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_campaign_deliveries_customer_id ON whatsapp_campaign_deliveries(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_campaign_deliveries_conversation_id ON whatsapp_campaign_deliveries(conversation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_campaign_deliveries_phone_normalized ON whatsapp_campaign_deliveries(phone_normalized)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_campaign_deliveries_provider_message_id ON whatsapp_campaign_deliveries(provider_message_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_campaign_deliveries_status ON whatsapp_campaign_deliveries(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_campaign_deliveries_sent_at ON whatsapp_campaign_deliveries(sent_at DESC)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_whatsapp_campaign_deliveries_provider_message
        ON whatsapp_campaign_deliveries(provider, provider_message_id)
        WHERE provider_message_id IS NOT NULL
        """
    )

    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS provider VARCHAR(40)")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS quoted_provider_message_id VARCHAR(255)")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS campaign_id VARCHAR")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS campaign_delivery_id VARCHAR")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_messages_provider ON agente_whatsapp_messages(provider)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_messages_quoted_provider_message_id ON agente_whatsapp_messages(quoted_provider_message_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_messages_campaign_id ON agente_whatsapp_messages(campaign_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_messages_campaign_delivery_id ON agente_whatsapp_messages(campaign_delivery_id)")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_agente_whatsapp_messages_campaign'
                  AND table_name = 'agente_whatsapp_messages'
            ) THEN
                ALTER TABLE agente_whatsapp_messages
                ADD CONSTRAINT fk_agente_whatsapp_messages_campaign
                FOREIGN KEY (campaign_id)
                REFERENCES whatsapp_campaigns(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_agente_whatsapp_messages_campaign_delivery'
                  AND table_name = 'agente_whatsapp_messages'
            ) THEN
                ALTER TABLE agente_whatsapp_messages
                ADD CONSTRAINT fk_agente_whatsapp_messages_campaign_delivery
                FOREIGN KEY (campaign_delivery_id)
                REFERENCES whatsapp_campaign_deliveries(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        INSERT INTO whatsapp_campaign_deliveries (
            id,
            tenant_id,
            company_id,
            whatsapp_message_id,
            campaign_id,
            template_id,
            customer_id,
            phone_normalized,
            recipient_name,
            provider,
            provider_message_id,
            message_type,
            message_text_snapshot,
            media_type,
            media_url,
            caption_snapshot,
            template_name_snapshot,
            campaign_name_snapshot,
            variables_json,
            provider_payload_json,
            status,
            sent_at,
            failed_at,
            created_at,
            updated_at
        )
        SELECT
            'wcd-' || wm.id,
            'default',
            'default',
            wm.id,
            wm.campaign_id,
            wm.template_id,
            wm.customer_id,
            regexp_replace(COALESCE(wm.phone, ''), '[^0-9]', '', 'g'),
            wm.recipient_name,
            COALESCE(wm.provider, 'official'),
            wm.wamid,
            COALESCE(wm.message_type, 'text'),
            wm.body_sent,
            wm.media_type,
            wm.media_url,
            wm.caption,
            wt.name,
            wc.name,
            '{}',
            json_build_object(
                'source', 'backfill_whatsapp_messages',
                'whatsapp_message_id', wm.id,
                'wamid', wm.wamid
            )::text,
            COALESCE(wm.status, 'pending'),
            wm.sent_at,
            CASE WHEN wm.status = 'failed' THEN COALESCE(wm.sent_at, wm.created_at) ELSE NULL END,
            COALESCE(wm.created_at, NOW()),
            NOW()
        FROM whatsapp_messages wm
        LEFT JOIN whatsapp_templates wt ON wt.id = wm.template_id
        LEFT JOIN whatsapp_campaigns wc ON wc.id = wm.campaign_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM whatsapp_campaign_deliveries existing
            WHERE existing.whatsapp_message_id = wm.id
        )
        """
    )

    op.execute(
        """
        UPDATE agente_whatsapp_messages awm
        SET
            provider = COALESCE(awm.provider, wcd.provider),
            campaign_id = COALESCE(awm.campaign_id, wcd.campaign_id),
            campaign_delivery_id = COALESCE(awm.campaign_delivery_id, wcd.id)
        FROM whatsapp_campaign_deliveries wcd
        WHERE (
            awm.provider_message_id = wcd.provider_message_id
            OR awm.provider_message_id = ('whatsapp-marketing:' || wcd.whatsapp_message_id)
        )
        """
    )
    op.execute(
        """
        UPDATE whatsapp_campaign_deliveries wcd
        SET
            conversation_id = awm.session_id,
            agente_message_id = awm.id,
            updated_at = NOW()
        FROM agente_whatsapp_messages awm
        WHERE awm.campaign_delivery_id = wcd.id
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_agente_whatsapp_messages_campaign_delivery'
                  AND table_name = 'agente_whatsapp_messages'
            ) THEN
                ALTER TABLE agente_whatsapp_messages
                DROP CONSTRAINT fk_agente_whatsapp_messages_campaign_delivery;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_agente_whatsapp_messages_campaign'
                  AND table_name = 'agente_whatsapp_messages'
            ) THEN
                ALTER TABLE agente_whatsapp_messages
                DROP CONSTRAINT fk_agente_whatsapp_messages_campaign;
            END IF;
        END $$;
        """
    )
    op.execute("DROP INDEX IF EXISTS ix_agente_whatsapp_messages_campaign_delivery_id")
    op.execute("DROP INDEX IF EXISTS ix_agente_whatsapp_messages_campaign_id")
    op.execute("DROP INDEX IF EXISTS ix_agente_whatsapp_messages_quoted_provider_message_id")
    op.execute("DROP INDEX IF EXISTS ix_agente_whatsapp_messages_provider")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS campaign_delivery_id")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS campaign_id")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS quoted_provider_message_id")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS provider")
    op.execute("DROP TABLE IF EXISTS whatsapp_campaign_deliveries")
