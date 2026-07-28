"""Expand tenant ownership for operations, freight, delivery and dining room.

Revision ID: 20260730_tenant_operations_expand
Revises: 20260729_tenant_payments_backfill
"""
from alembic import op
import sqlalchemy as sa


revision = "20260730_tenant_operations_expand"
down_revision = "20260729_tenant_payments_backfill"
branch_labels = None
depends_on = None


NEW_TENANT_COLUMNS = (
    "logistics_settings", "delivery_persons", "deliveries", "delivery_events",
    "delivery_earnings", "shipping_config", "freight_type_configs",
    "shipping_neighborhoods", "shipping_cep_ranges", "shipping_distance_rules",
    "shipping_order_value_tiers", "shipping_promotions", "shipping_extra_rules",
    "shipping_zones", "shipping_zone_areas", "shipping_rules", "restaurant_tables",
    "reservations", "table_sessions", "table_session_items", "salao_page_settings",
)

EXISTING_TENANT_COLUMNS = (
    "store_operation_settings", "store_weekly_schedules",
    "store_operation_intervals", "store_operation_exceptions", "store_operation_logs",
)

TABLES = NEW_TENANT_COLUMNS + EXISTING_TENANT_COLUMNS

SCOPED_UNIQUES = (
    ("uq_logistics_settings_tenant_singleton", "logistics_settings", "tenant_id", "tenant_id IS NOT NULL"),
    ("uq_shipping_config_tenant_singleton", "shipping_config", "tenant_id", "tenant_id IS NOT NULL"),
    ("uq_salao_page_settings_tenant_singleton", "salao_page_settings", "tenant_id", "tenant_id IS NOT NULL"),
    ("uq_store_operation_settings_tenant_singleton", "store_operation_settings", "tenant_id", "tenant_id IS NOT NULL"),
    ("uq_delivery_persons_tenant_email", "delivery_persons", "tenant_id, lower(email)", "email IS NOT NULL"),
    ("uq_deliveries_tenant_order", "deliveries", "tenant_id, order_id", None),
    ("uq_freight_type_configs_tenant_type", "freight_type_configs", "tenant_id, freight_type", None),
    ("uq_restaurant_tables_tenant_number", "restaurant_tables", "tenant_id, number", None),
)

COMPOSITE_FKS = (
    ("deliveries", "order_id", "orders", None),
    ("deliveries", "delivery_person_id", "delivery_persons", None),
    ("delivery_events", "delivery_id", "deliveries", "CASCADE"),
    ("delivery_earnings", "delivery_id", "deliveries", "CASCADE"),
    ("delivery_earnings", "delivery_person_id", "delivery_persons", "CASCADE"),
    ("shipping_zone_areas", "zone_id", "shipping_zones", None),
    ("shipping_rules", "zone_id", "shipping_zones", None),
    ("reservations", "customer_id", "customers", None),
    ("reservations", "table_id", "restaurant_tables", None),
    ("table_sessions", "table_id", "restaurant_tables", "RESTRICT"),
    ("table_sessions", "customer_id", "customers", None),
    ("table_session_items", "table_session_id", "table_sessions", "CASCADE"),
    ("table_session_items", "product_id", "products", "RESTRICT"),
    ("store_operation_intervals", "schedule_id", "store_weekly_schedules", "CASCADE"),
    ("orders", "table_session_id", "table_sessions", None),
)


def _tenant_fk(table: str) -> str:
    return f"fk_{table}_tenant_id_tenants"


def _pair_index(table: str) -> str:
    return f"uq_{table}_tenant_id_id"


def _composite_fk(table: str, column: str, parent: str) -> str:
    return f"fk_{table}_tenant_{column}_{parent}"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS logistics_settings (
            id VARCHAR PRIMARY KEY DEFAULT 'default',
            auto_assign BOOLEAN DEFAULT FALSE,
            max_concurrent_deliveries INTEGER DEFAULT 3,
            default_estimated_minutes INTEGER DEFAULT 40,
            confirmation_code_enabled BOOLEAN DEFAULT TRUE,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("INSERT INTO logistics_settings (id) VALUES ('default') ON CONFLICT DO NOTHING")
    op.execute(
        "ALTER TABLE delivery_persons "
        "ADD COLUMN IF NOT EXISTS email VARCHAR(200)"
    )

    for table in NEW_TENANT_COLUMNS:
        op.add_column(table, sa.Column("tenant_id", sa.String(), nullable=True))

    for table in EXISTING_TENANT_COLUMNS:
        op.alter_column(table, "tenant_id", existing_type=sa.String(length=80),
                        nullable=True, server_default=None)

    for table in TABLES:
        op.execute(sa.text(
            f"ALTER TABLE {table} ADD CONSTRAINT {_tenant_fk(table)} "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id) NOT VALID"
        ))
        op.create_index(_pair_index(table), table, ["tenant_id", "id"], unique=True)

    for name, table, columns, predicate in SCOPED_UNIQUES:
        where = f" WHERE {predicate}" if predicate else ""
        op.execute(sa.text(f"CREATE UNIQUE INDEX {name} ON {table} ({columns}){where}"))

    for table, column, parent, ondelete in COMPOSITE_FKS:
        delete = f" ON DELETE {ondelete}" if ondelete else ""
        op.execute(sa.text(
            f"ALTER TABLE {table} ADD CONSTRAINT {_composite_fk(table, column, parent)} "
            f"FOREIGN KEY (tenant_id, {column}) REFERENCES {parent} (tenant_id, id)"
            f"{delete} NOT VALID"
        ))


def downgrade() -> None:
    for table, column, parent, _ondelete in reversed(COMPOSITE_FKS):
        op.drop_constraint(_composite_fk(table, column, parent), table, type_="foreignkey")
    for name, table, _columns, _predicate in reversed(SCOPED_UNIQUES):
        op.drop_index(name, table_name=table)
    for table in reversed(TABLES):
        op.drop_index(_pair_index(table), table_name=table)
        op.drop_constraint(_tenant_fk(table), table, type_="foreignkey")
    for table in reversed(NEW_TENANT_COLUMNS):
        op.drop_column(table, "tenant_id")
