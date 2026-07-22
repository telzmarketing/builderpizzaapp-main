"""Contract tenant ownership for operations, freight and dining-room wave.

The migration aborts before DDL if any ownership is dirty.
"""
from hashlib import sha1
from alembic import op
import sqlalchemy as sa

revision = "20260808_tenant_operations_contract"
down_revision = "20260807_tenant_payments_contract"
branch_labels = None
depends_on = None

TABLES = (
    "logistics_settings", "delivery_persons", "deliveries", "delivery_events", "delivery_earnings", "shipping_config", "freight_type_configs", "shipping_neighborhoods", "shipping_cep_ranges", "shipping_distance_rules", "shipping_order_value_tiers", "shipping_promotions", "shipping_extra_rules", "shipping_zones", "shipping_zone_areas", "shipping_rules", "restaurant_tables", "reservations", "table_sessions", "table_session_items", "salao_page_settings", "store_operation_settings", "store_weekly_schedules", "store_operation_intervals", "store_operation_exceptions", "store_operation_logs",
)

def _name(prefix: str, *parts: str) -> str:
    raw = "_".join((prefix,) + parts)
    return raw if len(raw) <= 63 else f"{raw[:54]}_{sha1(raw.encode()).hexdigest()[:8]}"

def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        invalid = bind.execute(sa.text(f"SELECT 1 FROM {table} child LEFT JOIN tenants tenant ON tenant.id=child.tenant_id WHERE child.tenant_id IS NULL OR child.tenant_id='default' OR tenant.id IS NULL OR tenant.deleted_at IS NOT NULL LIMIT 1")).scalar()
        if invalid:
            raise RuntimeError(f"Contract gate failed for {table}: invalid tenant ownership")
    for table in TABLES:
        tenant_fk = f"fk_{table}_tenant_id_tenants"
        names = bind.execute(sa.text("SELECT con.conname FROM pg_constraint con JOIN pg_class rel ON rel.oid=con.conrelid JOIN pg_namespace ns ON ns.oid=rel.relnamespace WHERE ns.nspname=current_schema() AND rel.relname=:table AND con.contype='f' AND NOT con.convalidated AND (con.conname=:tenant_fk OR con.conname LIKE :fkmt)"), {"table": table, "tenant_fk": tenant_fk, "fkmt": "fkmt_%"}).scalars().all()
        for name in names:
            op.execute(sa.text(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{name}"'))
        op.alter_column(table, "tenant_id", existing_type=sa.String(), nullable=False, server_default=None)

def downgrade() -> None:
    for table in reversed(TABLES):
        op.alter_column(table, "tenant_id", existing_type=sa.String(), nullable=True)
