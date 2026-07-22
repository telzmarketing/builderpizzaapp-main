"""Backfill legacy ownership for backoffice data and address cache."""
from alembic import op
import sqlalchemy as sa

revision = "20260804_tenant_backoffice_async_backfill"
down_revision = "20260803_tenant_backoffice_async_expand"
branch_labels = None
depends_on = None
LEGACY_TENANT_ID = "tenant-legacy-default"
TABLES = (
    "gestao_module_settings", "inventory_units", "inventory_categories", "inventory_locations",
    "inventory_suppliers", "inventory_items", "inventory_purchases", "inventory_purchase_items",
    "inventory_manual_entries", "inventory_stock_movements", "inventory_recipe_versions",
    "inventory_recipe_items", "order_cmv_snapshots", "order_item_cmv_snapshots",
    "order_item_cmv_ingredient_snapshots", "finance_accounts", "finance_categories",
    "finance_counterparties", "finance_transactions", "finance_settlements", "fiscal_companies",
    "fiscal_certificates", "fiscal_series", "fiscal_product_profiles", "fiscal_documents",
    "fiscal_document_items", "fiscal_document_events", "geocode_cache",
)
UNIQUE_PREFLIGHTS = (
    ("gestao_module_settings", "module_key", "module_key IS NOT NULL"),
    ("order_cmv_snapshots", "order_id", "order_id IS NOT NULL"),
    ("fiscal_series", "document_model, environment, series", "document_model IS NOT NULL AND environment IS NOT NULL AND series IS NOT NULL"),
    ("fiscal_product_profiles", "product_id", "product_id IS NOT NULL"),
    ("finance_settlements", "idempotency_key", "idempotency_key IS NOT NULL"),
)
OWNERSHIP_PREFLIGHTS = (
    ("inventory_items", "category_id", "inventory_categories"), ("inventory_items", "unit_id", "inventory_units"),
    ("inventory_items", "default_location_id", "inventory_locations"), ("inventory_purchases", "supplier_id", "inventory_suppliers"),
    ("inventory_purchase_items", "purchase_id", "inventory_purchases"), ("inventory_purchase_items", "item_id", "inventory_items"),
    ("inventory_manual_entries", "item_id", "inventory_items"), ("inventory_manual_entries", "location_id", "inventory_locations"),
    ("inventory_stock_movements", "item_id", "inventory_items"), ("inventory_stock_movements", "location_id", "inventory_locations"),
    ("inventory_recipe_versions", "product_id", "products"), ("inventory_recipe_versions", "product_size_id", "product_sizes"),
    ("inventory_recipe_versions", "product_crust_type_id", "product_crust_types"), ("inventory_recipe_versions", "product_drink_variant_id", "product_drink_variants"),
    ("inventory_recipe_items", "recipe_id", "inventory_recipe_versions"), ("inventory_recipe_items", "inventory_item_id", "inventory_items"),
    ("order_cmv_snapshots", "order_id", "orders"), ("order_item_cmv_snapshots", "snapshot_id", "order_cmv_snapshots"),
    ("order_item_cmv_snapshots", "order_item_id", "order_items"), ("order_item_cmv_snapshots", "product_id", "products"),
    ("order_item_cmv_ingredient_snapshots", "item_snapshot_id", "order_item_cmv_snapshots"), ("order_item_cmv_ingredient_snapshots", "inventory_item_id", "inventory_items"),
    ("finance_categories", "parent_id", "finance_categories"), ("finance_transactions", "account_id", "finance_accounts"),
    ("finance_transactions", "category_id", "finance_categories"), ("finance_transactions", "counterparty_id", "finance_counterparties"),
    ("finance_transactions", "order_id", "orders"), ("finance_transactions", "payment_id", "payments"),
    ("finance_transactions", "inventory_purchase_id", "inventory_purchases"), ("finance_settlements", "transaction_id", "finance_transactions"),
    ("finance_settlements", "account_id", "finance_accounts"), ("fiscal_product_profiles", "product_id", "products"),
    ("fiscal_documents", "order_id", "orders"), ("fiscal_documents", "company_id", "fiscal_companies"),
    ("fiscal_documents", "series_id", "fiscal_series"), ("fiscal_document_items", "document_id", "fiscal_documents"),
    ("fiscal_document_items", "product_id", "products"), ("fiscal_document_events", "document_id", "fiscal_documents"),
)

def _effective(alias: str) -> str:
    return f"CASE WHEN {alias}.tenant_id IS NULL OR {alias}.tenant_id = 'default' THEN :tenant_id ELSE {alias}.tenant_id END"

def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(sa.text("SELECT 1 FROM tenants WHERE id = :tenant_id AND deleted_at IS NULL"), {"tenant_id": LEGACY_TENANT_ID}).scalar()
    if exists != 1:
        raise RuntimeError("Legacy tenant is missing; refusing backoffice backfill")
    for table in TABLES:
        invalid = bind.execute(sa.text(f"SELECT 1 FROM {table} child LEFT JOIN tenants tenant ON tenant.id = child.tenant_id WHERE child.tenant_id IS NOT NULL AND child.tenant_id <> 'default' AND tenant.id IS NULL LIMIT 1")).scalar()
        if invalid is not None:
            raise RuntimeError(f"Unknown tenant label in {table} blocks backfill")
    for table, columns, predicate in UNIQUE_PREFLIGHTS:
        duplicate = bind.execute(sa.text(f"SELECT 1 FROM {table} WHERE {predicate} GROUP BY CASE WHEN tenant_id IS NULL OR tenant_id = 'default' THEN :tenant_id ELSE tenant_id END, {columns} HAVING COUNT(*) > 1 LIMIT 1"), {"tenant_id": LEGACY_TENANT_ID}).scalar()
        if duplicate is not None:
            raise RuntimeError(f"Duplicate {table} ({columns}) blocks backfill")
    for table, column, parent in OWNERSHIP_PREFLIGHTS:
        mismatch = bind.execute(sa.text(f"SELECT 1 FROM {table} child JOIN {parent} parent ON parent.id = child.{column} WHERE child.{column} IS NOT NULL AND {_effective('child')} <> {_effective('parent')} LIMIT 1"), {"tenant_id": LEGACY_TENANT_ID}).scalar()
        if mismatch is not None:
            raise RuntimeError(f"Cross-tenant relationship {table}.{column} -> {parent}.id blocks backfill")
    for table in TABLES:
        bind.execute(sa.text(f"UPDATE {table} SET tenant_id = :tenant_id WHERE tenant_id IS NULL OR tenant_id = 'default'"), {"tenant_id": LEGACY_TENANT_ID})

def downgrade() -> None:
    # Ownership normalization is intentionally non-destructive.
    pass
