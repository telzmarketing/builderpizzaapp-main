"""Complete Master Central security, invitations, catalog and billing metadata.

Revision ID: 20260816_master_completion
Revises: 20260815_master_central_core
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260816_master_completion"
down_revision = "20260815_master_central_core"
branch_labels = None
depends_on = None


MODULE_CATALOG = (
    ("dashboard", "Dashboard", "operation", 10),
    ("products", "Produtos", "operation", 20),
    ("categories", "Categorias", "operation", 30),
    ("orders", "Pedidos e cozinha", "operation", 40),
    ("dine_in", "Salao", "operation", 50),
    ("customers", "Clientes", "operation", 60),
    ("coupons", "Cupons", "operation", 70),
    ("loyalty", "Fidelidade", "operation", 80),
    ("store_hours", "Funcionamento", "operation", 90),
    ("appearance", "Aparencia", "operation", 100),
    ("content", "Conteudo", "operation", 110),
    ("shipping", "Frete", "delivery", 10),
    ("delivery_zones", "Zonas de entrega", "delivery", 20),
    ("delivery", "Motoboys", "delivery", 30),
    ("logistics", "Logistica", "delivery", 40),
    ("tracking", "Rastreamento", "delivery", 50),
    ("reviews", "Avaliacao", "delivery", 60),
    ("inventory", "Estoque", "management", 10),
    ("cmv", "CMV", "management", 20),
    ("finance", "Financeiro", "management", 30),
    ("dre", "DRE", "management", 40),
    ("fiscal", "Fiscal", "management", 50),
    ("purchases", "Compras", "management", 60),
    ("suppliers", "Fornecedores", "management", 70),
    ("ingredients", "Insumos", "management", 80),
    ("marketing_dashboard", "Dashboard de marketing", "marketing", 10),
    ("marketing", "Campanhas", "marketing", 20),
    ("visitors", "Visitantes", "marketing", 30),
    ("links", "Links", "marketing", 40),
    ("marketing_integrations", "Integracoes de marketing", "marketing", 50),
    ("whatsapp", "WhatsApp", "marketing", 60),
    ("email", "E-mail", "marketing", 70),
    ("automations", "Automacoes", "marketing", 80),
    ("ads", "Anuncios", "marketing", 90),
    ("workflow", "Workflow", "marketing", 100),
    ("marketing_coupons", "Cupons de marketing", "marketing", 110),
    ("crm", "Dashboard CRM", "crm", 10),
    ("crm_intelligence", "Inteligencia CRM", "crm", 20),
    ("pipeline", "Pipeline", "crm", 30),
    ("groups", "Grupos", "crm", 40),
    ("tags", "Tags", "crm", 50),
    ("segments", "Segmentos", "crm", 60),
    ("tasks", "Tarefas", "crm", 70),
    ("payments", "Pagamentos", "integrations", 10),
    ("mercado_pago", "Mercado Pago", "integrations", 20),
    ("asaas", "Asaas", "integrations", 30),
    ("pix", "PIX", "integrations", 40),
    ("whatsapp_gateway", "WhatsApp Gateway", "integrations", 50),
    ("ai", "Inteligencia artificial", "integrations", 60),
    ("pixels", "Pixels", "integrations", 70),
    ("google", "Google", "integrations", 80),
    ("meta_ads", "Meta Ads", "integrations", 90),
    ("webhooks", "Webhooks", "integrations", 100),
    ("integrations", "API e integracoes externas", "integrations", 110),
)


def upgrade() -> None:
    # The original global UNIQUE(name) conflicts with tenant-scoped role names.
    # tenant_id is already NOT NULL since 20260805; the existing composite
    # constraint protects names independently inside each tenant.
    op.execute(
        """
        ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_name_key
        """
    )

    for name, type_ in (
        ("segment", sa.String(120)),
        ("whatsapp", sa.String(30)),
        ("billing_email", sa.String(200)),
        ("internal_code", sa.String(80)),
        ("logo_url", sa.String(500)),
        ("legal_representative_document", sa.String(30)),
    ):
        op.add_column("tenant_profiles", sa.Column(name, type_, nullable=True))

    op.add_column(
        "saas_plans",
        sa.Column("plan_type", sa.String(20), nullable=False, server_default="public"),
    )
    op.create_check_constraint(
        "ck_saas_plans_type", "saas_plans", "plan_type IN ('public','custom')"
    )
    for name in ("monthly_price", "quarterly_price", "semiannual_price", "annual_price"):
        op.add_column("saas_plans", sa.Column(name, sa.Numeric(18, 2), nullable=True))
    op.add_column(
        "saas_plans",
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        """
        UPDATE saas_plans
        SET monthly_price = price
        WHERE billing_cycle = 'monthly' AND monthly_price IS NULL
        """
    )
    op.execute(
        """
        UPDATE saas_plans
        SET quarterly_price = price
        WHERE billing_cycle = 'quarterly' AND quarterly_price IS NULL
        """
    )
    op.execute(
        """
        UPDATE saas_plans
        SET semiannual_price = price
        WHERE billing_cycle = 'semiannual' AND semiannual_price IS NULL
        """
    )
    op.execute(
        """
        UPDATE saas_plans
        SET annual_price = price
        WHERE billing_cycle = 'annual' AND annual_price IS NULL
        """
    )

    op.add_column("tenant_licenses", sa.Column("contract_value", sa.Numeric(18, 2)))
    op.add_column("tenant_licenses", sa.Column("next_due_at", sa.DateTime(timezone=True)))
    op.add_column("support_sessions", sa.Column("exchanged_at", sa.DateTime(timezone=True)))
    op.add_column("support_sessions", sa.Column("last_seen_at", sa.DateTime(timezone=True)))
    op.add_column(
        "admin_users",
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("admin_users", sa.Column("job_title", sa.String(120)))

    op.create_table(
        "tenant_invitations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(30)),
        sa.Column("job_title", sa.String(120)),
        sa.Column("membership_role", sa.String(30), nullable=False, server_default="viewer"),
        sa.Column("role_id", sa.String(), sa.ForeignKey("roles.id", ondelete="SET NULL")),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "invited_by",
            sa.String(),
            sa.ForeignKey("admin_users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "accepted_by",
            sa.String(),
            sa.ForeignKey("admin_users.id", ondelete="SET NULL"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("resend_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending','accepted','expired','revoked')",
            name="ck_tenant_invitations_status",
        ),
    )
    op.create_index(
        "ix_tenant_invitations_tenant_status",
        "tenant_invitations",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_tenant_invitations_email_status",
        "tenant_invitations",
        ["email", "status"],
    )
    op.create_index(
        "uq_tenant_invitations_pending_email",
        "tenant_invitations",
        ["tenant_id", "email"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    modules = sa.table(
        "saas_modules",
        sa.column("id", sa.String()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("module_group", sa.String()),
        sa.column("active", sa.Boolean()),
        sa.column("display_order", sa.Integer()),
        sa.column("dependencies_json", sa.Text()),
        sa.column("default_config_json", sa.Text()),
    )
    module_rows = [
            {
                "id": f"catalog_{key}",
                "key": key,
                "name": name,
                "description": f"Modulo base: {name}.",
                "module_group": group,
                "active": True,
                "display_order": order,
                "dependencies_json": "[]",
                "default_config_json": "{}",
            }
            for key, name, group, order in MODULE_CATALOG
        ]
    op.get_bind().execute(
        postgresql.insert(modules)
        .values(module_rows)
        .on_conflict_do_nothing(index_elements=["key"])
    )
    # Preserve commercial intent: only materialize plan-module relationships
    # already expressed by current subscriptions and origin='plan' entitlements.
    op.execute(
        """
        INSERT INTO saas_plan_modules (id, plan_id, module_id, enabled, created_at)
        SELECT
            'seed_' || s.plan_id || '_' || tm.module_id,
            s.plan_id,
            tm.module_id,
            true,
            now()
        FROM tenant_subscriptions s
        JOIN tenant_modules tm
          ON tm.tenant_id = s.tenant_id
         AND tm.origin = 'plan'
         AND tm.enabled = true
        WHERE s.ended_at IS NULL
          AND s.plan_id IS NOT NULL
        ON CONFLICT (plan_id, module_id) DO NOTHING
        """
    )


def downgrade() -> None:
    catalog_ids = ", ".join(f"'catalog_{key}'" for key, _name, _group, _order in MODULE_CATALOG)
    op.execute(
        """
        DELETE FROM saas_plan_modules
        WHERE id = 'seed_' || plan_id || '_' || module_id
        """
    )
    op.execute(
        f"""
        DELETE FROM saas_modules m
        WHERE m.id IN ({catalog_ids})
          AND NOT EXISTS (
              SELECT 1 FROM tenant_modules tm WHERE tm.module_id = m.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM saas_plan_modules pm WHERE pm.module_id = m.id
          )
        """
    )
    op.drop_index("uq_tenant_invitations_pending_email", table_name="tenant_invitations")
    op.drop_index("ix_tenant_invitations_email_status", table_name="tenant_invitations")
    op.drop_index("ix_tenant_invitations_tenant_status", table_name="tenant_invitations")
    op.drop_table("tenant_invitations")
    op.drop_column("admin_users", "job_title")
    op.drop_column("admin_users", "auth_version")
    op.drop_column("support_sessions", "last_seen_at")
    op.drop_column("support_sessions", "exchanged_at")
    op.drop_column("tenant_licenses", "next_due_at")
    op.drop_column("tenant_licenses", "contract_value")
    op.drop_column("saas_plans", "trial_days")
    for name in ("annual_price", "semiannual_price", "quarterly_price", "monthly_price"):
        op.drop_column("saas_plans", name)
    op.drop_constraint("ck_saas_plans_type", "saas_plans", type_="check")
    op.drop_column("saas_plans", "plan_type")
    for name in (
        "legal_representative_document",
        "logo_url",
        "internal_code",
        "billing_email",
        "whatsapp",
        "segment",
    ):
        op.drop_column("tenant_profiles", name)

    # Fail before changing the constraint if tenant-scoped data can no longer
    # satisfy the historical global uniqueness rule. Never delete or rename
    # business roles during downgrade.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM roles GROUP BY name HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot restore roles_name_key: duplicate role names exist across tenants';
            END IF;
        END $$
        """
    )
    op.create_unique_constraint("roles_name_key", "roles", ["name"])
