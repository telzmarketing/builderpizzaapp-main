"""Contract tenant ownership for identity and catalog wave.

This migration is intentionally fail-closed. It validates the database state
before making tenant ownership mandatory; it never guesses a legacy tenant.
Global unique constraints are not removed here because their names and live
usage must be approved by the operational contract gate.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260805_tenant_catalog_contract"
down_revision = "20260804_tenant_backoffice_async_backfill"
branch_labels = None
depends_on = None


TABLES = (
    "roles", "role_permissions", "user_permissions", "admin_audit_logs",
    "products", "product_categories", "product_sizes", "product_crust_types",
    "product_drink_variants", "best_seller_config", "multi_flavors_config",
    "product_promotions", "product_promotion_combinations", "promotions",
    "promotion_landing_pages", "campaigns", "campaign_products",
    "promotional_kits", "promotional_kit_items", "upsells", "upsell_metrics",
    "upsell_events", "order_upsells", "home_catalog_config", "theme_settings",
)


def _contract(table: str) -> None:
    bind = op.get_bind()
    invalid = bind.execute(sa.text(
        f"SELECT 1 FROM {table} child LEFT JOIN tenants tenant ON tenant.id = child.tenant_id "
        "WHERE child.tenant_id IS NULL OR child.tenant_id = 'default' "
        "OR tenant.id IS NULL OR tenant.deleted_at IS NOT NULL LIMIT 1"
    )).scalar()
    if invalid:
        raise RuntimeError(f"Contract gate failed for {table}: invalid tenant ownership")
    constraints = bind.execute(sa.text(
        "SELECT con.conname FROM pg_constraint con "
        "JOIN pg_class rel ON rel.oid = con.conrelid "
        "JOIN pg_namespace ns ON ns.oid = rel.relnamespace "
        "WHERE ns.nspname = current_schema() AND rel.relname = :table "
        "AND con.contype = 'f' AND NOT con.convalidated "
        "AND (con.conname = :tenant_fk OR con.conname LIKE :composite_fk)"
    ), {"table": table, "tenant_fk": f"fk_{table}_tenant_id_tenants",
        "composite_fk": f"fk_{table}_tenant_%"}).scalars().all()
    for constraint in constraints:
        op.execute(sa.text(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{constraint}"'))
    op.alter_column(table, "tenant_id", existing_type=sa.String(),
                    nullable=False, server_default=None)


def upgrade() -> None:
    for table in TABLES:
        _contract(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.alter_column(table, "tenant_id", existing_type=sa.String(), nullable=True)
