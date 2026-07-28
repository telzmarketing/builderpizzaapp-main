"""Expand tenant ownership for customers, consumer identity and orders.

Revision ID: 20260726_tenant_customers_orders_expand
Revises: 20260725_tenant_domains
"""
from alembic import op
import sqlalchemy as sa


revision = "20260726_tenant_customers_orders_expand"
down_revision = "20260725_tenant_domains"
branch_labels = None
depends_on = None


TABLES = (
    "customers",
    "addresses",
    "lgpd_policies",
    "customer_auth",
    "customer_channels",
    "customer_preferences",
    "orders",
    "order_items",
    "order_item_flavors",
    "customer_events",
)

SCOPED_UNIQUE_INDEXES = (
    ("uq_customers_tenant_email", "customers", "tenant_id, email", None),
    ("uq_customers_tenant_google_id", "customers", "tenant_id, google_id", "google_id IS NOT NULL"),
    ("uq_customer_auth_tenant_customer_provider", "customer_auth", "tenant_id, customer_id, auth_provider", None),
    ("uq_customer_auth_tenant_provider_identifier", "customer_auth", "tenant_id, auth_provider, identifier", "identifier IS NOT NULL"),
    ("uq_customer_channels_tenant_identifier", "customer_channels", "tenant_id, channel, normalized_identifier", None),
    ("uq_customer_preferences_tenant_customer", "customer_preferences", "tenant_id, customer_id", None),
    ("uq_orders_tenant_order_code", "orders", "tenant_id, order_code", "order_code IS NOT NULL"),
    ("uq_orders_tenant_external_reference", "orders", "tenant_id, external_reference", "external_reference IS NOT NULL"),
)

COMPOSITE_FKS = (
    ("addresses", "customer_id", "customers", "CASCADE"),
    ("customer_auth", "customer_id", "customers", "CASCADE"),
    ("customer_channels", "customer_id", "customers", "CASCADE"),
    ("customer_preferences", "customer_id", "customers", "CASCADE"),
    ("orders", "customer_id", "customers", "NO ACTION"),
    ("orders", "address_id", "addresses", "NO ACTION"),
    ("order_items", "order_id", "orders", "CASCADE"),
    ("order_items", "product_id", "products", "RESTRICT"),
    ("order_item_flavors", "order_item_id", "order_items", "CASCADE"),
    ("order_item_flavors", "product_id", "products", "RESTRICT"),
    ("customer_events", "customer_id", "customers", "NO ACTION"),
    ("customer_events", "order_id", "orders", "NO ACTION"),
    ("customer_events", "product_id", "products", "NO ACTION"),
)


def _tenant_fk(table: str) -> str:
    return f"fk_{table}_tenant_id_tenants"


def _pair_index(table: str) -> str:
    return f"uq_{table}_tenant_id_id"


def _composite_fk(table: str, column: str, parent: str) -> str:
    return f"fk_{table}_tenant_{column}_{parent}"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_code VARCHAR(10)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_order_code "
        "ON orders(order_code) WHERE order_code IS NOT NULL"
    )

    for table in TABLES:
        op.add_column(table, sa.Column("tenant_id", sa.String(), nullable=True))
        op.execute(sa.text(
            f"ALTER TABLE {table} ADD CONSTRAINT {_tenant_fk(table)} "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id) NOT VALID"
        ))
        op.create_index(_pair_index(table), table, ["tenant_id", "id"], unique=True)

    for name, table, columns, predicate in SCOPED_UNIQUE_INDEXES:
        where = f" WHERE {predicate}" if predicate else ""
        op.execute(sa.text(
            f"CREATE UNIQUE INDEX {name} ON {table} ({columns}){where}"
        ))

    for table, column, parent, ondelete in COMPOSITE_FKS:
        op.execute(sa.text(
            f"ALTER TABLE {table} ADD CONSTRAINT {_composite_fk(table, column, parent)} "
            f"FOREIGN KEY (tenant_id, {column}) REFERENCES {parent} (tenant_id, id) "
            f"ON DELETE {ondelete} NOT VALID"
        ))


def downgrade() -> None:
    for table, column, parent, _ondelete in reversed(COMPOSITE_FKS):
        op.drop_constraint(_composite_fk(table, column, parent), table, type_="foreignkey")
    for name, table, _columns, _predicate in reversed(SCOPED_UNIQUE_INDEXES):
        op.drop_index(name, table_name=table)
    for table in reversed(TABLES):
        op.drop_index(_pair_index(table), table_name=table)
        op.drop_constraint(_tenant_fk(table), table, type_="foreignkey")
        op.drop_column(table, "tenant_id")
