"""Expand tenant ownership for backoffice data and address cache.

Revision ID: 20260803_tenant_backoffice_async_expand
Revises: 20260802_tenant_marketing_crm_whatsapp_backfill
"""
from hashlib import sha1

from alembic import op
import sqlalchemy as sa


revision = "20260803_tenant_backoffice_async_expand"
down_revision = "20260802_tenant_marketing_crm_whatsapp_backfill"
branch_labels = None
depends_on = None


# Child tables did not carry ownership in the legacy schema. GeocodeCache is
# not a proven global cache: it persists the normalized address in `query`.
NEW_TENANT_COLUMNS = (
    "inventory_purchase_items",
    "inventory_recipe_items",
    "fiscal_document_items",
    "geocode_cache",
)

EXISTING_TENANT_COLUMNS = (
    "gestao_module_settings",
    "inventory_units", "inventory_categories", "inventory_locations",
    "inventory_suppliers", "inventory_items", "inventory_purchases",
    "inventory_manual_entries", "inventory_stock_movements",
    "inventory_recipe_versions",
    "order_cmv_snapshots", "order_item_cmv_snapshots",
    "order_item_cmv_ingredient_snapshots",
    "finance_accounts", "finance_categories", "finance_counterparties",
    "finance_transactions", "finance_settlements",
    "fiscal_companies", "fiscal_certificates", "fiscal_series",
    "fiscal_product_profiles", "fiscal_documents", "fiscal_document_events",
)

TABLES = NEW_TENANT_COLUMNS + EXISTING_TENANT_COLUMNS

# These keys are enforced by current services or by an existing global unique.
# The legacy global constraint remains until contract.
SCOPED_UNIQUES = (
    ("uq_mt_gestao_module_settings_key", "gestao_module_settings", "tenant_id, module_key", None),
    ("uq_mt_order_cmv_snapshot_order", "order_cmv_snapshots", "tenant_id, order_id", None),
    ("uq_mt_fiscal_series_model_env_series", "fiscal_series", "tenant_id, document_model, environment, series", None),
    ("uq_mt_fiscal_product_profile_product", "fiscal_product_profiles", "tenant_id, product_id", None),
    ("uq_mt_finance_settlement_idempotency", "finance_settlements", "tenant_id, idempotency_key", "idempotency_key IS NOT NULL"),
)

COMPOSITE_FKS = (
    ("inventory_items", "category_id", "inventory_categories", "NO ACTION"),
    ("inventory_items", "unit_id", "inventory_units", "NO ACTION"),
    ("inventory_items", "default_location_id", "inventory_locations", "NO ACTION"),
    ("inventory_purchases", "supplier_id", "inventory_suppliers", "NO ACTION"),
    ("inventory_purchase_items", "purchase_id", "inventory_purchases", "CASCADE"),
    ("inventory_purchase_items", "item_id", "inventory_items", "NO ACTION"),
    ("inventory_manual_entries", "item_id", "inventory_items", "NO ACTION"),
    ("inventory_manual_entries", "location_id", "inventory_locations", "NO ACTION"),
    ("inventory_stock_movements", "item_id", "inventory_items", "NO ACTION"),
    ("inventory_stock_movements", "location_id", "inventory_locations", "NO ACTION"),
    ("inventory_recipe_versions", "product_id", "products", "CASCADE"),
    ("inventory_recipe_versions", "product_size_id", "product_sizes", "NO ACTION"),
    ("inventory_recipe_versions", "product_crust_type_id", "product_crust_types", "NO ACTION"),
    ("inventory_recipe_versions", "product_drink_variant_id", "product_drink_variants", "NO ACTION"),
    ("inventory_recipe_items", "recipe_id", "inventory_recipe_versions", "CASCADE"),
    ("inventory_recipe_items", "inventory_item_id", "inventory_items", "NO ACTION"),
    ("order_cmv_snapshots", "order_id", "orders", "CASCADE"),
    ("order_item_cmv_snapshots", "snapshot_id", "order_cmv_snapshots", "CASCADE"),
    ("order_item_cmv_snapshots", "order_item_id", "order_items", "CASCADE"),
    ("order_item_cmv_snapshots", "product_id", "products", "NO ACTION"),
    ("order_item_cmv_ingredient_snapshots", "item_snapshot_id", "order_item_cmv_snapshots", "CASCADE"),
    ("order_item_cmv_ingredient_snapshots", "inventory_item_id", "inventory_items", "NO ACTION"),
    ("finance_categories", "parent_id", "finance_categories", "NO ACTION"),
    ("finance_transactions", "account_id", "finance_accounts", "NO ACTION"),
    ("finance_transactions", "category_id", "finance_categories", "NO ACTION"),
    ("finance_transactions", "counterparty_id", "finance_counterparties", "NO ACTION"),
    ("finance_transactions", "order_id", "orders", "NO ACTION"),
    ("finance_transactions", "payment_id", "payments", "NO ACTION"),
    ("finance_transactions", "inventory_purchase_id", "inventory_purchases", "NO ACTION"),
    ("finance_settlements", "transaction_id", "finance_transactions", "CASCADE"),
    ("finance_settlements", "account_id", "finance_accounts", "NO ACTION"),
    ("fiscal_product_profiles", "product_id", "products", "CASCADE"),
    ("fiscal_documents", "order_id", "orders", "NO ACTION"),
    ("fiscal_documents", "company_id", "fiscal_companies", "NO ACTION"),
    ("fiscal_documents", "series_id", "fiscal_series", "NO ACTION"),
    ("fiscal_document_items", "document_id", "fiscal_documents", "CASCADE"),
    ("fiscal_document_items", "product_id", "products", "NO ACTION"),
    ("fiscal_document_events", "document_id", "fiscal_documents", "CASCADE"),
)


def _name(prefix: str, *parts: str) -> str:
    raw = "_".join((prefix,) + parts)
    return raw if len(raw) <= 63 else f"{raw[:54]}_{sha1(raw.encode()).hexdigest()[:8]}"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS geocode_cache (
            id VARCHAR(32) PRIMARY KEY,
            query TEXT NOT NULL,
            lat FLOAT,
            lng FLOAT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )

    for table in NEW_TENANT_COLUMNS:
        op.execute(sa.text(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_id VARCHAR"
        ))

    for table in EXISTING_TENANT_COLUMNS:
        op.alter_column(table, "tenant_id", existing_type=sa.String(), nullable=True, server_default=None)

    for table in TABLES:
        op.execute(sa.text(
            f"ALTER TABLE {table} ADD CONSTRAINT {_name('fk', table, 'tenant')} "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id) NOT VALID"
        ))
        op.create_index(_name("uq", table, "tenant_id_id"), table, ["tenant_id", "id"], unique=True)

    for name, table, columns, predicate in SCOPED_UNIQUES:
        where = f" WHERE {predicate}" if predicate else ""
        op.execute(sa.text(f"CREATE UNIQUE INDEX {name} ON {table} ({columns}){where}"))

    for table, column, parent, ondelete in COMPOSITE_FKS:
        delete = " ON DELETE CASCADE" if ondelete == "CASCADE" else ""
        op.execute(sa.text(
            f"ALTER TABLE {table} ADD CONSTRAINT {_name('fkmt', table, column)} "
            f"FOREIGN KEY (tenant_id, {column}) REFERENCES {parent} (tenant_id, id)"
            f"{delete} NOT VALID"
        ))


def downgrade() -> None:
    for table, column, _parent, _ondelete in reversed(COMPOSITE_FKS):
        op.drop_constraint(_name("fkmt", table, column), table, type_="foreignkey")
    for name, table, _columns, _predicate in reversed(SCOPED_UNIQUES):
        op.drop_index(name, table_name=table)
    for table in reversed(TABLES):
        op.drop_index(_name("uq", table, "tenant_id_id"), table_name=table)
        op.drop_constraint(_name("fk", table, "tenant"), table, type_="foreignkey")
    for table in reversed(NEW_TENANT_COLUMNS):
        op.drop_column(table, "tenant_id")
