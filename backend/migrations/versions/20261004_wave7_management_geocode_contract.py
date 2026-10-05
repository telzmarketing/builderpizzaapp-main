"""Contract Management and geocode ownership before the Wave 7 rollout.

Management tables were expanded in the original Operations wave and
``geocode_cache`` in the Backoffice wave.  This final forward-only migration
does not assign legacy rows to a default tenant: it stops if ownership is not
already proven, then makes the address cache ownership mandatory.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261004_wave7_management_geocode_contract"
down_revision = "20261004_wave7_fiscal_contract"
branch_labels = None
depends_on = None


MANAGEMENT_TABLES = (
    "gestao_module_settings",
    "store_operation_settings",
    "store_weekly_schedules",
    "store_operation_intervals",
    "store_operation_exceptions",
    "store_operation_logs",
)
GEOCODE_TABLE = "geocode_cache"


def _invalid_ownership(bind, table: str) -> bool:
    return bool(bind.execute(sa.text(f"""
        SELECT 1
        FROM {table} child
        LEFT JOIN tenants tenant ON tenant.id = child.tenant_id
        WHERE child.tenant_id IS NULL OR child.tenant_id = 'default'
           OR tenant.id IS NULL OR tenant.deleted_at IS NOT NULL
        LIMIT 1
    """)).scalar())


def _validate_tenant_constraints(bind, table: str) -> None:
    names = bind.execute(sa.text("""
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace ns ON ns.oid = rel.relnamespace
        WHERE ns.nspname = current_schema()
          AND rel.relname = :table
          AND con.contype = 'f'
          AND NOT con.convalidated
          AND pg_get_constraintdef(con.oid) ILIKE '%FOREIGN KEY (tenant_id)%'
    """), {"table": table}).scalars().all()
    for name in names:
        op.execute(sa.text(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{name}"'))


def upgrade() -> None:
    bind = op.get_bind()
    for table in MANAGEMENT_TABLES + (GEOCODE_TABLE,):
        if _invalid_ownership(bind, table):
            raise RuntimeError(f"Wave 7 management/geocode: tenant ownership invalido em {table}")

    # ``geocode_cache.query`` contains an address and must never be shared
    # across companies.  The service additionally namespaces its hash key.
    _validate_tenant_constraints(bind, GEOCODE_TABLE)
    op.alter_column(GEOCODE_TABLE, "tenant_id", existing_type=sa.String(), nullable=False)
    op.create_index(
        "ix_geocode_cache_tenant_created_at",
        GEOCODE_TABLE,
        ["tenant_id", "created_at"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    # A downgrade must not make personally identifying address cache entries
    # global again.  Keep this boundary once data has been tenantized.
    pass
