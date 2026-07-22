"""Backfill legacy tenant ownership for order payments and gateway configuration."""
from alembic import op
import sqlalchemy as sa


revision = "20260729_tenant_payments_backfill"
down_revision = "20260728_tenant_payments_expand"
branch_labels = None
depends_on = None


LEGACY_TENANT_ID = "tenant-legacy-default"
BACKFILL_ORDER = (
    "payment_gateway_config",
    "payments",
    "payment_events",
    "payment_provider_customers",
)

UNIQUE_PREFLIGHTS = (
    ("payments", "order_id", "order_id IS NOT NULL"),
    ("payments", "provider, provider_payment_id", "provider_payment_id IS NOT NULL"),
    ("payments", "mercado_pago_payment_id", "mercado_pago_payment_id IS NOT NULL"),
    ("payment_events", "provider, provider_event_id", "provider_event_id IS NOT NULL"),
    ("payment_provider_customers", "customer_id, provider", "customer_id IS NOT NULL"),
    (
        "payment_provider_customers",
        "provider, provider_customer_id",
        "provider_customer_id IS NOT NULL",
    ),
)

OWNERSHIP_PREFLIGHTS = (
    ("payments", "order_id", "orders"),
    ("payment_provider_customers", "customer_id", "customers"),
)


def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(
        sa.text("SELECT 1 FROM tenants WHERE id = :tenant_id AND deleted_at IS NULL"),
        {"tenant_id": LEGACY_TENANT_ID},
    ).scalar()
    if exists != 1:
        raise RuntimeError("Legacy tenant is missing; refusing payments backfill")

    config_count = bind.execute(sa.text(
        "SELECT COUNT(*) FROM payment_gateway_config "
        "WHERE tenant_id IS NULL OR tenant_id = :tenant_id"
    ), {"tenant_id": LEGACY_TENANT_ID}).scalar()
    if config_count and config_count > 1:
        raise RuntimeError("Multiple payment gateway configs block legacy tenant backfill")

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
