"""gestao phase 1 base

Revision ID: 20260625_gestao_phase1_base
Revises: 20260624_customer_lead_email_domain
"""
from __future__ import annotations

from alembic import op

revision = "20260625_gestao_phase1_base"
down_revision = "20260624_customer_lead_email_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS gestao_module_settings (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            module_key VARCHAR(40) NOT NULL,
            title VARCHAR(120) NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            status VARCHAR(40) NOT NULL DEFAULT 'disabled',
            settings_json TEXT NOT NULL DEFAULT '{}',
            notes TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_gestao_module_settings_tenant_module ON gestao_module_settings(tenant_id, module_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_gestao_module_settings_tenant_id ON gestao_module_settings(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_gestao_module_settings_module_key ON gestao_module_settings(module_key)")

    op.execute(
        """
        INSERT INTO gestao_module_settings (id, tenant_id, module_key, title, description, enabled, status, settings_json, notes)
        VALUES
            ('gestao-default-inventory', 'default', 'inventory', 'Estoque', 'Cadastros e configuracoes para controle de insumos, saldos e disponibilidade.', FALSE, 'disabled', '{"auto_consume_on_preparing": false, "negative_stock_policy": "warn_only", "sales_control_enabled": false, "out_of_stock_behavior": "show_unavailable", "alerts_enabled": false}', 'Nasce desabilitado. Nao altera pedidos, checkout ou cozinha nesta fase.'),
            ('gestao-default-cmv', 'default', 'cmv', 'CMV', 'Base para custo de mercadoria vendida, snapshots e classificacao da DRE.', FALSE, 'disabled', '{"mode": "disabled", "target_percent": null, "estimated_mode_allowed": true}', 'Analitico e sem side effects. Nao bloqueia pedido nem interfere na cozinha.'),
            ('gestao-default-finance', 'default', 'finance', 'Financeiro', 'Base para contas, lancamentos, recebiveis, caixa, competencia e DRE.', FALSE, 'disabled', '{"auto_create_receivables": false, "auto_create_payables_from_purchases": false, "default_receivable_account_id": null, "default_payable_account_id": null, "cash_basis_enabled": true, "accrual_basis_enabled": true, "dre_enabled": true}', 'Nao substitui PaymentService nesta fase.'),
            ('gestao-default-fiscal', 'default', 'fiscal', 'Fiscal SEFAZ', 'Base para fiscal nativo com SEFAZ direta, sem Saipos ou middleware fiscal.', FALSE, 'disabled', '{"sefaz_integration_enabled": false, "environment": "homologation", "certificate_configured": false, "external_middleware_allowed": false, "default_document_model": "NFCe"}', 'Preparacao cadastral. Nenhum XML e transmitido nesta fase.')
        ON CONFLICT (id) DO NOTHING
        """
    )

    modules = [
        ("gestao-module-inventory", "inventory", "Estoque", 28),
        ("gestao-module-cmv", "cmv", "CMV", 29),
        ("gestao-module-finance", "finance", "Financeiro ERP", 30),
        ("gestao-module-fiscal", "fiscal", "Fiscal SEFAZ", 31),
    ]
    for module_id, key, name, order in modules:
        op.execute(
            f"""
            INSERT INTO rbac_modules (id, key, name, order_index, is_active)
            VALUES ('{module_id}', '{key}', '{name}', {order}, TRUE)
            ON CONFLICT (key) DO NOTHING
            """
        )

    role_permissions = {
        "master": {
            "inventory": ["view", "create", "edit", "delete", "approve", "export", "manage"],
            "cmv": ["view", "create", "edit", "delete", "approve", "export", "manage"],
            "finance": ["view", "create", "edit", "delete", "approve", "export", "manage"],
            "fiscal": ["view", "create", "edit", "delete", "approve", "export", "manage"],
        },
        "administrador": {
            "inventory": ["view", "create", "edit", "export", "manage"],
            "cmv": ["view", "export", "manage"],
            "finance": ["view", "create", "edit", "approve", "export", "manage"],
            "fiscal": ["view", "create", "edit", "export", "manage"],
        },
        "gerente": {
            "inventory": ["view", "create", "edit", "export"],
            "cmv": ["view", "export"],
            "finance": ["view", "export"],
            "fiscal": ["view"],
        },
        "financeiro": {
            "inventory": ["view", "export"],
            "cmv": ["view", "export"],
            "finance": ["view", "create", "edit", "approve", "export", "manage"],
            "fiscal": ["view", "export"],
        },
    }
    for role, modules_for_role in role_permissions.items():
        for module_key, permissions in modules_for_role.items():
            for permission in permissions:
                op.execute(
                    f"""
                    INSERT INTO role_permissions (id, role_id, module_id, permission_id, allowed)
                    SELECT 'gestao-rp-{role}-{module_key}-{permission}', r.id, m.id, p.id, TRUE
                    FROM roles r, rbac_modules m, rbac_permissions p
                    WHERE r.name = '{role}'
                      AND m.key = '{module_key}'
                      AND p.key = '{permission}'
                      AND NOT EXISTS (
                          SELECT 1 FROM role_permissions rp
                          WHERE rp.role_id = r.id
                            AND rp.module_id = m.id
                            AND rp.permission_id = p.id
                      )
                    """
                )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE id LIKE 'gestao-rp-%'")
    op.execute("DELETE FROM rbac_modules WHERE key IN ('inventory', 'cmv', 'finance', 'fiscal')")
    op.execute("DROP TABLE IF EXISTS gestao_module_settings")
