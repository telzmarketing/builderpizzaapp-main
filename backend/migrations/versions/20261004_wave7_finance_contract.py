"""Verify and repair the finance ownership contract required by Wave 7.

Revision ID: 20261004_wave7_finance_contract
Revises: 20261003_agente_whatsapp_tenant_foundation

The original backoffice expand/backfill/contract series introduced the
financial tenant columns and composite foreign keys.  This final contract
gate is deliberately defensive: an upgraded database with manually removed
constraints is repaired only after cross-company references are proven absent.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261004_wave7_finance_contract"
down_revision = "20261003_agente_whatsapp_tenant_foundation"
branch_labels = None
depends_on = None


TABLES = (
    "finance_accounts",
    "finance_categories",
    "finance_counterparties",
    "finance_transactions",
    "finance_settlements",
)

OWNERSHIP_PAIRS = (
    ("finance_categories", "parent_id", "finance_categories", "NO ACTION"),
    ("finance_transactions", "account_id", "finance_accounts", "NO ACTION"),
    ("finance_transactions", "category_id", "finance_categories", "NO ACTION"),
    ("finance_transactions", "counterparty_id", "finance_counterparties", "NO ACTION"),
    ("finance_transactions", "order_id", "orders", "NO ACTION"),
    ("finance_transactions", "payment_id", "payments", "NO ACTION"),
    ("finance_transactions", "inventory_purchase_id", "inventory_purchases", "NO ACTION"),
    ("finance_settlements", "transaction_id", "finance_transactions", "CASCADE"),
    ("finance_settlements", "account_id", "finance_accounts", "NO ACTION"),
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
            raise RuntimeError(f"Wave 7 financeiro: tenant ownership invalido em {table}")

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
                "Wave 7 financeiro: relacionamento entre empresas bloqueia a migracao "
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
    # Removing an ownership boundary can expose valid multi-tenant records.
    pass
