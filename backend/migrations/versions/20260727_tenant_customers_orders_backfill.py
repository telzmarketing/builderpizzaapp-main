"""Backfill legacy tenant ownership for customers, identity and orders."""
from alembic import op
import sqlalchemy as sa

revision = "20260727_tenant_customers_orders_backfill"
down_revision = "20260726_tenant_customers_orders_expand"
branch_labels = None
depends_on = None

LEGACY_TENANT_ID = "tenant-legacy-default"
BACKFILL_ORDER = (
    "customers", "lgpd_policies", "addresses", "customer_auth",
    "customer_channels", "customer_preferences", "orders", "order_items",
    "order_item_flavors", "customer_events",
)
UNIQUE_PREFLIGHTS = (
    ("customers", "email", "email IS NOT NULL"),
    ("customers", "google_id", "google_id IS NOT NULL"),
    ("customer_auth", "customer_id, auth_provider", "customer_id IS NOT NULL"),
    ("customer_auth", "auth_provider, identifier", "identifier IS NOT NULL"),
    ("customer_channels", "channel, normalized_identifier", "normalized_identifier IS NOT NULL"),
    ("customer_preferences", "customer_id", "customer_id IS NOT NULL"),
    ("orders", "order_code", "order_code IS NOT NULL"),
    ("orders", "external_reference", "external_reference IS NOT NULL"),
)
OWNERSHIP_PREFLIGHTS = (
    ("addresses", "customer_id", "customers"),
    ("customer_auth", "customer_id", "customers"),
    ("customer_channels", "customer_id", "customers"),
    ("customer_preferences", "customer_id", "customers"),
    ("orders", "customer_id", "customers"),
    ("orders", "address_id", "addresses"),
    ("order_items", "order_id", "orders"),
    ("order_items", "product_id", "products"),
    ("order_item_flavors", "order_item_id", "order_items"),
    ("order_item_flavors", "product_id", "products"),
    ("customer_events", "customer_id", "customers"),
    ("customer_events", "order_id", "orders"),
    ("customer_events", "product_id", "products"),
)


def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(
        sa.text("SELECT 1 FROM tenants WHERE id = :tenant_id AND deleted_at IS NULL"),
        {"tenant_id": LEGACY_TENANT_ID},
    ).scalar()
    if exists != 1:
        raise RuntimeError("Legacy tenant is missing; refusing customers/orders backfill")

    for table, columns, predicate in UNIQUE_PREFLIGHTS:
        duplicate = bind.execute(
            sa.text(
                f"SELECT 1 FROM {table} WHERE {predicate} "
                "AND (tenant_id IS NULL OR tenant_id = :tenant_id) "
                f"GROUP BY {columns} HAVING COUNT(*) > 1 LIMIT 1"
            ),
            {"tenant_id": LEGACY_TENANT_ID},
        ).scalar()
        if duplicate is not None:
            raise RuntimeError(f"Duplicate {table} ({columns}) blocks legacy tenant backfill")

    for table, column, parent in OWNERSHIP_PREFLIGHTS:
        mismatch = bind.execute(
            sa.text(
                f"SELECT 1 FROM {table} child JOIN {parent} parent ON parent.id = child.{column} "
                f"WHERE child.{column} IS NOT NULL "
                "AND COALESCE(child.tenant_id, :tenant_id) <> "
                "COALESCE(parent.tenant_id, :tenant_id) LIMIT 1"
            ),
            {"tenant_id": LEGACY_TENANT_ID},
        ).scalar()
        if mismatch is not None:
            raise RuntimeError(
                f"Cross-tenant relationship {table}.{column} -> {parent}.id blocks backfill"
            )

    for table in BACKFILL_ORDER:
        bind.execute(
            sa.text(f"UPDATE {table} SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
            {"tenant_id": LEGACY_TENANT_ID},
        )


def downgrade() -> None:
    # Tenant attribution is business data and must not be erased on rollback.
    pass
