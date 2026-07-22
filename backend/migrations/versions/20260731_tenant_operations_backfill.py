"""Backfill legacy tenant ownership for operations, freight and dining room."""
from alembic import op
import sqlalchemy as sa

revision = "20260731_tenant_operations_backfill"
down_revision = "20260730_tenant_operations_expand"
branch_labels = None
depends_on = None

LEGACY_TENANT_ID = "tenant-legacy-default"
BACKFILL_ORDER = (
    "logistics_settings", "shipping_config", "freight_type_configs",
    "shipping_neighborhoods", "shipping_cep_ranges", "shipping_distance_rules",
    "shipping_order_value_tiers", "shipping_promotions", "shipping_extra_rules",
    "shipping_zones", "shipping_zone_areas", "shipping_rules", "delivery_persons",
    "deliveries", "delivery_events", "delivery_earnings", "restaurant_tables",
    "reservations", "table_sessions", "table_session_items", "salao_page_settings",
    "store_operation_settings", "store_weekly_schedules", "store_operation_intervals",
    "store_operation_exceptions", "store_operation_logs",
)
UNIQUE_PREFLIGHTS = (
    ("delivery_persons", "lower(email)", "email IS NOT NULL"),
    ("deliveries", "order_id", "order_id IS NOT NULL"),
    ("freight_type_configs", "freight_type", "freight_type IS NOT NULL"),
    ("restaurant_tables", "number", "number IS NOT NULL"),
)
SINGLETON_PREFLIGHTS = (
    "logistics_settings", "shipping_config", "salao_page_settings",
    "store_operation_settings",
)
OWNERSHIP_PREFLIGHTS = (
    ("deliveries", "order_id", "orders"),
    ("deliveries", "delivery_person_id", "delivery_persons"),
    ("delivery_events", "delivery_id", "deliveries"),
    ("delivery_earnings", "delivery_id", "deliveries"),
    ("delivery_earnings", "delivery_person_id", "delivery_persons"),
    ("shipping_zone_areas", "zone_id", "shipping_zones"),
    ("shipping_rules", "zone_id", "shipping_zones"),
    ("reservations", "customer_id", "customers"),
    ("reservations", "table_id", "restaurant_tables"),
    ("table_sessions", "table_id", "restaurant_tables"),
    ("table_sessions", "customer_id", "customers"),
    ("table_session_items", "table_session_id", "table_sessions"),
    ("table_session_items", "product_id", "products"),
    ("store_operation_intervals", "schedule_id", "store_weekly_schedules"),
    ("orders", "table_session_id", "table_sessions"),
)

def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(
        sa.text("SELECT 1 FROM tenants WHERE id = :tenant_id AND deleted_at IS NULL"),
        {"tenant_id": LEGACY_TENANT_ID},
    ).scalar()
    if exists != 1:
        raise RuntimeError("Legacy tenant is missing; refusing operations backfill")

    for table in BACKFILL_ORDER:
        invalid = bind.execute(sa.text(
            f"SELECT 1 FROM {table} child LEFT JOIN tenants tenant ON tenant.id = child.tenant_id "
            "WHERE child.tenant_id IS NOT NULL AND child.tenant_id <> 'default' "
            "AND tenant.id IS NULL LIMIT 1"
        )).scalar()
        if invalid is not None:
            raise RuntimeError(f"Unknown tenant label in {table} blocks operations backfill")

    for table, columns, predicate in UNIQUE_PREFLIGHTS:
        duplicate = bind.execute(sa.text(
            f"SELECT 1 FROM {table} WHERE {predicate} "
            "GROUP BY CASE WHEN tenant_id IS NULL OR tenant_id = 'default' "
            "THEN :tenant_id ELSE tenant_id END, "
            f"{columns} HAVING COUNT(*) > 1 LIMIT 1"
        ), {"tenant_id": LEGACY_TENANT_ID}).scalar()
        if duplicate is not None:
            raise RuntimeError(f"Duplicate {table} ({columns}) blocks operations backfill")

    for table in SINGLETON_PREFLIGHTS:
        count = bind.execute(sa.text(
            f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NULL "
            "OR tenant_id = 'default' OR tenant_id = :tenant_id"
        ), {"tenant_id": LEGACY_TENANT_ID}).scalar()
        if count and count > 1:
            raise RuntimeError(f"Multiple {table} rows block legacy tenant backfill")

    for table, column, parent in OWNERSHIP_PREFLIGHTS:
        mismatch = bind.execute(sa.text(
            f"SELECT 1 FROM {table} child JOIN {parent} parent ON parent.id = child.{column} "
            f"WHERE child.{column} IS NOT NULL AND "
            "CASE WHEN child.tenant_id IS NULL OR child.tenant_id = 'default' THEN :tenant_id ELSE child.tenant_id END <> "
            "CASE WHEN parent.tenant_id IS NULL OR parent.tenant_id = 'default' THEN :tenant_id ELSE parent.tenant_id END LIMIT 1"
        ), {"tenant_id": LEGACY_TENANT_ID}).scalar()
        if mismatch is not None:
            raise RuntimeError(f"Cross-tenant relationship {table}.{column} -> {parent}.id blocks backfill")

    for table in BACKFILL_ORDER:
        bind.execute(sa.text(
            f"UPDATE {table} SET tenant_id = :tenant_id "
            "WHERE tenant_id IS NULL OR tenant_id = 'default'"
        ), {"tenant_id": LEGACY_TENANT_ID})


def downgrade() -> None:
    pass
