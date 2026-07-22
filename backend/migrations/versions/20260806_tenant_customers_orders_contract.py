"""Contract tenant ownership for customers and orders wave."""
from alembic import op
import sqlalchemy as sa

revision = "20260806_tenant_customers_orders_contract"
down_revision = "20260805_tenant_catalog_contract"
branch_labels = None
depends_on = None

TABLES = ("customers", "addresses", "lgpd_policies", "customer_auth",
          "customer_channels", "customer_preferences", "orders", "order_items",
          "order_item_flavors", "customer_events")


def _contract(table: str) -> None:
    bind = op.get_bind()
    invalid = bind.execute(sa.text(
        f"SELECT 1 FROM {table} child LEFT JOIN tenants tenant ON tenant.id = child.tenant_id "
        "WHERE child.tenant_id IS NULL OR child.tenant_id = 'default' OR tenant.id IS NULL "
        "OR tenant.deleted_at IS NOT NULL LIMIT 1"
    )).scalar()
    if invalid:
        raise RuntimeError(f"Contract gate failed for {table}: invalid tenant ownership")
    names = bind.execute(sa.text(
        "SELECT con.conname FROM pg_constraint con JOIN pg_class rel ON rel.oid=con.conrelid "
        "JOIN pg_namespace ns ON ns.oid=rel.relnamespace WHERE ns.nspname=current_schema() "
        "AND rel.relname=:table AND con.contype='f' AND NOT con.convalidated "
        "AND (con.conname=:tenant_fk OR con.conname LIKE :composite_fk)"
    ), {"table": table, "tenant_fk": f"fk_{table}_tenant_id_tenants",
        "composite_fk": f"fk_{table}_tenant_%"}).scalars().all()
    for name in names:
        op.execute(sa.text(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{name}"'))
    op.alter_column(table, "tenant_id", existing_type=sa.String(), nullable=False,
                    server_default=None)


def upgrade() -> None:
    for table in TABLES:
        _contract(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.alter_column(table, "tenant_id", existing_type=sa.String(), nullable=True)
