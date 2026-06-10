"""whatsapp provider consolidation

Revision ID: 20260610_whatsapp_provider_consolidation
Revises: 20260605_whatsapp_gateway_base
"""

from alembic import op

revision = "20260610_whatsapp_provider_consolidation"
down_revision = "20260605_whatsapp_gateway_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE whatsapp_config ADD COLUMN IF NOT EXISTS whatsapp_gateway_instance_id VARCHAR")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_whatsapp_config_gateway_instance'
                  AND table_name = 'whatsapp_config'
            ) THEN
                ALTER TABLE whatsapp_config
                ADD CONSTRAINT fk_whatsapp_config_gateway_instance
                FOREIGN KEY (whatsapp_gateway_instance_id)
                REFERENCES whatsapp_gateway_instances(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        UPDATE whatsapp_config
        SET connection_type = 'official',
            status = 'disconnected'
        WHERE connection_type IN ('evolution', 'uazapi', 'qr')
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agente_whatsapp_channel_settings (
            id VARCHAR PRIMARY KEY DEFAULT 'default',
            active_provider VARCHAR(40) NOT NULL DEFAULT 'official',
            whatsapp_gateway_instance_id VARCHAR REFERENCES whatsapp_gateway_instances(id) ON DELETE SET NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        INSERT INTO agente_whatsapp_channel_settings (
            id, active_provider, whatsapp_gateway_instance_id, updated_at
        )
        VALUES ('default', 'official', NULL, NOW())
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE agente_whatsapp_provider_states
        SET provider = 'baileys'
        WHERE provider IN ('whatsapp_gateway', 'gateway')
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_channel_settings")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_whatsapp_config_gateway_instance'
                  AND table_name = 'whatsapp_config'
            ) THEN
                ALTER TABLE whatsapp_config DROP CONSTRAINT fk_whatsapp_config_gateway_instance;
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE whatsapp_config DROP COLUMN IF EXISTS whatsapp_gateway_instance_id")
