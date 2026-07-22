"""Contract tenant ownership for backoffice and async/cache wave."""
from alembic import op
import sqlalchemy as sa

revision = "20260810_tenant_backoffice_contract"
down_revision = "20260809_tenant_marketing_contract"
branch_labels = None
depends_on = None

TABLES = (
    "inventory_purchase_items", "inventory_recipe_items", "fiscal_document_items", "geocode_cache", "gestao_module_settings", "inventory_units", "inventory_categories", "inventory_locations", "inventory_suppliers", "inventory_items", "inventory_purchases", "inventory_manual_entries", "inventory_stock_movements", "inventory_recipe_versions", "order_cmv_snapshots", "order_item_cmv_snapshots", "order_item_cmv_ingredient_snapshots", "finance_accounts", "finance_categories", "finance_counterparties", "finance_transactions", "finance_settlements", "fiscal_companies", "fiscal_certificates", "fiscal_series", "fiscal_product_profiles", "fiscal_documents", "fiscal_document_events",
)

def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        invalid = bind.execute(sa.text(f"SELECT 1 FROM {table} child LEFT JOIN tenants tenant ON tenant.id=child.tenant_id WHERE child.tenant_id IS NULL OR child.tenant_id='default' OR tenant.id IS NULL OR tenant.deleted_at IS NOT NULL LIMIT 1")).scalar()
        if invalid:
            raise RuntimeError(f"Contract gate failed for {table}: invalid tenant ownership")
    for table in TABLES:
        names = bind.execute(sa.text("SELECT con.conname FROM pg_constraint con JOIN pg_class rel ON rel.oid=con.conrelid JOIN pg_namespace ns ON ns.oid=rel.relnamespace WHERE ns.nspname=current_schema() AND rel.relname=:table AND con.contype='f' AND NOT con.convalidated AND (con.conname=:tenant_fk OR con.conname LIKE :fkmt)"), {"table": table, "tenant_fk": f"fk_{table}_tenant_id_tenants", "fkmt": "fkmt_%"}).scalars().all()
        for name in names:
            op.execute(sa.text(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{name}"'))
        op.alter_column(table, "tenant_id", existing_type=sa.String(), nullable=False, server_default=None)

def downgrade() -> None:
    for table in reversed(TABLES):
        op.alter_column(table, "tenant_id", existing_type=sa.String(), nullable=True)
