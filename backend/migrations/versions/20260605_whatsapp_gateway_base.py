"""whatsapp gateway base

Revision ID: 20260605_whatsapp_gateway_base
Revises: 20260527_whatsapp_uazapi_unofficial
"""

from alembic import op

revision = "20260605_whatsapp_gateway_base"
down_revision = "20260527_whatsapp_uazapi_unofficial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_gateway_instances (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            company_id VARCHAR(80) NOT NULL DEFAULT 'default',
            name VARCHAR(180) NOT NULL,
            phone_number VARCHAR(40),
            provider VARCHAR(40) NOT NULL DEFAULT 'baileys',
            status VARCHAR(40) NOT NULL DEFAULT 'created',
            session_key VARCHAR(255),
            qr_code TEXT,
            connected_at TIMESTAMPTZ,
            disconnected_at TIMESTAMPTZ,
            last_seen_at TIMESTAMPTZ,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_instances_tenant_id ON whatsapp_gateway_instances(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_instances_company_id ON whatsapp_gateway_instances(company_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_instances_phone_number ON whatsapp_gateway_instances(phone_number)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_instances_provider ON whatsapp_gateway_instances(provider)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_instances_status ON whatsapp_gateway_instances(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_instances_created_at ON whatsapp_gateway_instances(created_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_gateway_logs (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            company_id VARCHAR(80) NOT NULL DEFAULT 'default',
            instance_id VARCHAR REFERENCES whatsapp_gateway_instances(id) ON DELETE SET NULL,
            action VARCHAR(80) NOT NULL,
            status VARCHAR(40) NOT NULL DEFAULT 'info',
            message TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_logs_tenant_id ON whatsapp_gateway_logs(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_logs_company_id ON whatsapp_gateway_logs(company_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_logs_instance_id ON whatsapp_gateway_logs(instance_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_logs_action ON whatsapp_gateway_logs(action)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_logs_status ON whatsapp_gateway_logs(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_logs_created_at ON whatsapp_gateway_logs(created_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_gateway_update_logs (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            company_id VARCHAR(80) NOT NULL DEFAULT 'default',
            package_name VARCHAR(160) NOT NULL DEFAULT '@whiskeysockets/baileys',
            current_version VARCHAR(80),
            available_version VARCHAR(80),
            update_type VARCHAR(30),
            risk_level VARCHAR(30),
            environment VARCHAR(40) NOT NULL DEFAULT 'production',
            action VARCHAR(80) NOT NULL DEFAULT 'check',
            status VARCHAR(40) NOT NULL DEFAULT 'pending',
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            error_message TEXT,
            rollback_version VARCHAR(80),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_update_logs_tenant_id ON whatsapp_gateway_update_logs(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_update_logs_company_id ON whatsapp_gateway_update_logs(company_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_update_logs_status ON whatsapp_gateway_update_logs(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_update_logs_created_at ON whatsapp_gateway_update_logs(created_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_gateway_scheduler_settings (
            id VARCHAR PRIMARY KEY DEFAULT 'default',
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            company_id VARCHAR(80) NOT NULL DEFAULT 'default',
            auto_health_check_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            morning_check_time VARCHAR(5) NOT NULL DEFAULT '06:00',
            evening_check_time VARCHAR(5) NOT NULL DEFAULT '18:00',
            auto_update_check_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            auto_update_staging_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            auto_update_production_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            notify_admin_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_scheduler_settings_tenant_id ON whatsapp_gateway_scheduler_settings(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_whatsapp_gateway_scheduler_settings_company_id ON whatsapp_gateway_scheduler_settings(company_id)")
    op.execute(
        """
        INSERT INTO whatsapp_gateway_scheduler_settings (id)
        VALUES ('default')
        ON CONFLICT (id) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO rbac_modules (id, key, name, description, order_index, is_active, created_at)
        VALUES (
            'rbac-module-whatsapp-gateway',
            'whatsapp_gateway',
            'WhatsApp Gateway',
            'Infraestrutura de conexao WhatsApp Web, Baileys, sessoes, saude e atualizacoes',
            23,
            TRUE,
            NOW()
        )
        ON CONFLICT (key) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (id, role_id, module_id, permission_id, allowed)
        SELECT
            'roleperm-whatsapp-gateway-' || r.name || '-' || p.key,
            r.id,
            m.id,
            p.id,
            TRUE
        FROM roles r
        JOIN rbac_modules m ON m.key = 'whatsapp_gateway'
        JOIN rbac_permissions p ON p.key IN ('view', 'create', 'edit', 'manage')
        WHERE r.name IN ('master', 'administrador')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE id LIKE 'roleperm-whatsapp-gateway-%'")
    op.execute("DELETE FROM rbac_modules WHERE key = 'whatsapp_gateway'")
    op.execute("DROP TABLE IF EXISTS whatsapp_gateway_scheduler_settings")
    op.execute("DROP TABLE IF EXISTS whatsapp_gateway_update_logs")
    op.execute("DROP TABLE IF EXISTS whatsapp_gateway_logs")
    op.execute("DROP TABLE IF EXISTS whatsapp_gateway_instances")
