"""Validate Fiscal ownership before enabling the Wave 7 boundary.

The previous backoffice migration series expanded Fiscal with tenant columns
and composite foreign keys.  This forward-only gate verifies existing data and
repairs a missing composite ownership constraint only after it is proven safe.
It deliberately never assigns a legacy row to a tenant.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261004_wave7_fiscal_contract"
down_revision = "20261004_wave7_finance_contract"
branch_labels = None
depends_on = None


TABLES = (
    "fiscal_companies",
    "fiscal_certificates",
    "fiscal_series",
    "fiscal_product_profiles",
    "fiscal_documents",
    "fiscal_document_items",
    "fiscal_document_events",
)

OWNERSHIP_PAIRS = (
    ("fiscal_product_profiles", "product_id", "products", "CASCADE"),
    ("fiscal_documents", "order_id", "orders", "NO ACTION"),
    ("fiscal_documents", "company_id", "fiscal_companies", "NO ACTION"),
    ("fiscal_documents", "series_id", "fiscal_series", "NO ACTION"),
    ("fiscal_document_items", "document_id", "fiscal_documents", "CASCADE"),
    ("fiscal_document_items", "product_id", "products", "NO ACTION"),
    ("fiscal_document_events", "document_id", "fiscal_documents", "CASCADE"),
)


def _constraint_name(table: str, column: str) -> str:
    return f"fk_wave7_{table}_{column}"


def _has_composite_fk(bind, table: str, column: str, parent: str) -> bool:
    return bool(bind.execute(sa.text("""
        SELECT 1
        FROM pg_constraint con
        JOIN pg_class child ON child.oid = con.conrelid
        JOIN pg_class parent_rel ON parent_rel.oid = con.confrelid
        JOIN pg_namespace ns ON ns.oid = child.relnamespace
        WHERE ns.nspname = current_schema()
          AND con.contype = 'f'
          AND child.relname = :table
          AND parent_rel.relname = :parent
          AND pg_get_constraintdef(con.oid) ILIKE :signature
        LIMIT 1
    """), {
        "table": table,
        "parent": parent,
        "signature": f"%FOREIGN KEY (tenant_id, {column}) REFERENCES {parent}(tenant_id, id)%",
    }).scalar())


def _validate_composite_fks(bind, table: str) -> None:
    names = bind.execute(sa.text("""
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace ns ON ns.oid = rel.relnamespace
        WHERE ns.nspname = current_schema()
          AND rel.relname = :table
          AND con.contype = 'f'
          AND NOT con.convalidated
          AND pg_get_constraintdef(con.oid) ILIKE '%FOREIGN KEY (tenant_id,%'
    """), {"table": table}).scalars().all()
    for name in names:
        op.execute(sa.text(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{name}"'))


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        invalid = bind.execute(sa.text(f"""
            SELECT 1
            FROM {table} child
            LEFT JOIN tenants tenant ON tenant.id = child.tenant_id
            WHERE child.tenant_id IS NULL OR child.tenant_id = 'default'
               OR tenant.id IS NULL OR tenant.deleted_at IS NOT NULL
            LIMIT 1
        """)).scalar()
        if invalid is not None:
            raise RuntimeError(f"Wave 7 fiscal: tenant ownership invalido em {table}")

    for child_table, column, parent_table, ondelete in OWNERSHIP_PAIRS:
        mismatch = bind.execute(sa.text(f"""
            SELECT 1
            FROM {child_table} child
            JOIN {parent_table} parent ON parent.id = child.{column}
            WHERE child.{column} IS NOT NULL
              AND child.tenant_id <> parent.tenant_id
            LIMIT 1
        """)).scalar()
        if mismatch is not None:
            raise RuntimeError(
                "Wave 7 fiscal: relacionamento entre empresas bloqueia a migracao "
                f"({child_table}.{column} -> {parent_table}.id)"
            )
        if not _has_composite_fk(bind, child_table, column, parent_table):
            delete = " ON DELETE CASCADE" if ondelete == "CASCADE" else ""
            op.execute(sa.text(
                f"ALTER TABLE {child_table} ADD CONSTRAINT {_constraint_name(child_table, column)} "
                f"FOREIGN KEY (tenant_id, {column}) REFERENCES {parent_table} (tenant_id, id)"
                f"{delete} NOT VALID"
            ))

    for table in TABLES:
        _validate_composite_fks(bind, table)


def downgrade() -> None:
    # Never remove an ownership boundary from a live multi-tenant database.
    pass
