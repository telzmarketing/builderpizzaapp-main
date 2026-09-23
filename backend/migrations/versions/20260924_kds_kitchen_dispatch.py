"""Add tenant KDS kitchen/dispatch flow and fulfillment ownership.

Revision ID: 20260924_kds_kitchen_dispatch
Revises: 20260923_pagarme_tenant_gateway
"""
from alembic import op
import sqlalchemy as sa


revision = "20260924_kds_kitchen_dispatch"
down_revision = "20260923_pagarme_tenant_gateway"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("fulfillment_type", sa.String(20), nullable=False, server_default="delivery"),
    )
    op.execute("UPDATE orders SET fulfillment_type = 'dine_in' WHERE sales_channel = 'dine_in'")
    op.execute(
        "UPDATE orders SET fulfillment_type = 'pickup' "
        "WHERE sales_channel <> 'dine_in' AND lower(trim(coalesce(delivery_street, ''))) = 'retirada no local'"
    )
    op.create_check_constraint(
        "ck_orders_fulfillment_type", "orders",
        "fulfillment_type IN ('delivery','pickup','dine_in')",
    )
    op.create_index(
        "ix_orders_tenant_fulfillment_status", "orders",
        ["tenant_id", "fulfillment_type", "status"],
    )
    op.alter_column(
        "orders", "fulfillment_type", existing_type=sa.String(20),
        nullable=False, server_default=None,
    )

    op.execute("""
        INSERT INTO rbac_modules (id, key, name, description, order_index, is_active, created_at)
        VALUES ('rbac-module-expedicao', 'expedicao', 'Expedicao (KDS)',
                'Conferencia e atribuicao de motoboy', 28, TRUE, NOW())
        ON CONFLICT (key) DO UPDATE SET name = EXCLUDED.name,
            description = EXCLUDED.description, is_active = TRUE
    """)
    op.execute("""
        INSERT INTO roles (id, tenant_id, name, description, is_system, created_at, updated_at)
        SELECT 'kds-expedicao-' || md5(t.id), t.id, 'expedicao',
               'Expedicao - operacao exclusiva do KDS', TRUE, NOW(), NOW()
        FROM tenants t
        WHERE NOT EXISTS (
            SELECT 1 FROM roles r WHERE r.tenant_id = t.id AND lower(r.name) = 'expedicao'
        )
    """)
    op.execute("""
        UPDATE roles SET is_system = TRUE
        WHERE lower(name) IN ('cozinha', 'expedicao')
    """)
    op.execute("""
        DELETE FROM role_permissions rp USING roles r, rbac_modules m
        WHERE rp.role_id = r.id AND rp.module_id = m.id
          AND lower(r.name) = 'cozinha' AND m.key <> 'cozinha'
    """)
    op.execute("""
        DELETE FROM role_permissions rp USING roles r, rbac_modules m
        WHERE rp.role_id = r.id AND rp.module_id = m.id
          AND lower(r.name) = 'expedicao' AND m.key <> 'expedicao'
    """)
    for role_name, module_key in (("cozinha", "cozinha"), ("expedicao", "expedicao")):
        for permission_key in ("view", "edit"):
            op.execute(sa.text("""
                INSERT INTO role_permissions
                    (id, tenant_id, role_id, module_id, permission_id, allowed)
                SELECT 'kds-rp-' || md5(r.id || m.id || p.id), r.tenant_id,
                       r.id, m.id, p.id, TRUE
                FROM roles r CROSS JOIN rbac_modules m CROSS JOIN rbac_permissions p
                WHERE lower(r.name) = :role_name AND m.key = :module_key
                  AND p.key = :permission_key
                  AND NOT EXISTS (
                    SELECT 1 FROM role_permissions rp
                    WHERE rp.role_id = r.id AND rp.module_id = m.id AND rp.permission_id = p.id
                  )
            """).bindparams(
                role_name=role_name,
                module_key=module_key,
                permission_key=permission_key,
            ))


def downgrade() -> None:
    op.execute("""
        DELETE FROM role_permissions rp USING roles r
        WHERE rp.role_id = r.id AND lower(r.name) = 'expedicao'
    """)
    op.execute("DELETE FROM roles WHERE lower(name) = 'expedicao' AND is_system = TRUE")
    op.execute("DELETE FROM rbac_modules WHERE key = 'expedicao'")
    op.drop_index("ix_orders_tenant_fulfillment_status", table_name="orders")
    op.drop_constraint("ck_orders_fulfillment_type", "orders", type_="check")
    op.drop_column("orders", "fulfillment_type")
