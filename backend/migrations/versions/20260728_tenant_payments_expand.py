"""Expand tenant ownership for order payments and gateway configuration.

Revision ID: 20260728_tenant_payments_expand
Revises: 20260727_tenant_customers_orders_backfill
"""
from alembic import op
import sqlalchemy as sa


revision = "20260728_tenant_payments_expand"
down_revision = "20260727_tenant_customers_orders_backfill"
branch_labels = None
depends_on = None


TABLES = (
    "payments",
    "payment_events",
    "payment_provider_customers",
    "payment_gateway_config",
)

SCOPED_UNIQUE_INDEXES = (
    ("uq_payments_tenant_order_id", "payments", "tenant_id, order_id", None),
    (
        "uq_payments_tenant_provider_payment_id",
        "payments",
        "tenant_id, provider, provider_payment_id",
        "provider_payment_id IS NOT NULL",
    ),
    (
        "uq_payments_tenant_mercado_pago_payment_id",
        "payments",
        "tenant_id, mercado_pago_payment_id",
        "mercado_pago_payment_id IS NOT NULL",
    ),
    (
        "uq_payment_events_tenant_provider_event_id",
        "payment_events",
        "tenant_id, provider, provider_event_id",
        "provider_event_id IS NOT NULL",
    ),
    (
        "uq_payment_provider_customers_tenant_customer_provider",
        "payment_provider_customers",
        "tenant_id, customer_id, provider",
        None,
    ),
    (
        "uq_payment_provider_customers_tenant_provider_external",
        "payment_provider_customers",
        "tenant_id, provider, provider_customer_id",
        None,
    ),
    (
        "uq_payment_gateway_config_tenant_singleton",
        "payment_gateway_config",
        "tenant_id",
        "tenant_id IS NOT NULL",
    ),
)

COMPOSITE_FKS = (
    ("payments", "order_id", "orders", "CASCADE"),
    ("payment_provider_customers", "customer_id", "customers", "CASCADE"),
)


def _tenant_fk(table: str) -> str:
    return f"fk_{table}_tenant_id_tenants"


def _pair_index(table: str) -> str:
    return f"uq_{table}_tenant_id_id"


def _composite_fk(table: str, column: str, parent: str) -> str:
    return f"fk_{table}_tenant_{column}_{parent}"


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("tenant_id", sa.String(), nullable=True))
        op.execute(sa.text(
            f"ALTER TABLE {table} ADD CONSTRAINT {_tenant_fk(table)} "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id) NOT VALID"
        ))
        op.create_index(_pair_index(table), table, ["tenant_id", "id"], unique=True)

    for name, table, columns, predicate in SCOPED_UNIQUE_INDEXES:
        where = f" WHERE {predicate}" if predicate else ""
        op.execute(sa.text(f"CREATE UNIQUE INDEX {name} ON {table} ({columns}){where}"))

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
