"""Finish the Wave 7 logistics ownership contract without legacy backfill."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261004_wave7_logistics_identity_contract"
down_revision = "20261004_wave7_management_geocode_contract"
branch_labels = None
depends_on = None

LOGISTICS_TABLES = ("delivery_persons", "deliveries", "delivery_events", "delivery_earnings")
OWNERSHIP_PAIRS = (
    ("deliveries", "order_id", "orders", None),
    ("deliveries", "delivery_person_id", "delivery_persons", None),
    ("delivery_events", "delivery_id", "deliveries", "CASCADE"),
    ("delivery_earnings", "delivery_id", "deliveries", "CASCADE"),
    ("delivery_earnings", "delivery_person_id", "delivery_persons", "CASCADE"),
)
SCOPED_UNIQUES = (
    ("uq_delivery_persons_tenant_email", "delivery_persons", "tenant_id, lower(email)", "email IS NOT NULL"),
    ("uq_deliveries_tenant_order", "deliveries", "tenant_id, order_id", None),
    ("uq_freight_type_configs_tenant_type", "freight_type_configs", "tenant_id, freight_type", None),
)


def _invalid_ownership(bind, table: str) -> bool:
    return bool(bind.execute(sa.text(f"""
        SELECT 1 FROM {table} child
        LEFT JOIN tenants tenant ON tenant.id = child.tenant_id
        WHERE child.tenant_id IS NULL OR child.tenant_id = 'default'
           OR tenant.id IS NULL OR tenant.deleted_at IS NOT NULL
        LIMIT 1
    """)).scalar())


def _assert_same_tenant_references(bind) -> None:
    for child, column, parent, _ondelete in OWNERSHIP_PAIRS:
        invalid = bind.execute(sa.text(f"""
            SELECT 1 FROM {child} c JOIN {parent} p ON p.id = c.{column}
            WHERE c.{column} IS NOT NULL AND c.tenant_id <> p.tenant_id LIMIT 1
        """)).scalar()
        if invalid is not None:
            raise RuntimeError(
                "Wave 7 logistica: relacionamento entre empresas bloqueia a migracao "
                f"({child}.{column} -> {parent}.id)"
            )


def _assert_scoped_unique_rows(bind, table: str, expression: str, where: str | None) -> None:
    predicate = f"WHERE {where}" if where else ""
    duplicate = bind.execute(sa.text(f"""
        SELECT 1 FROM {table} {predicate}
        GROUP BY {expression} HAVING COUNT(*) > 1 LIMIT 1
    """)).scalar()
    if duplicate is not None:
        raise RuntimeError(f"Wave 7 logistica: identidade por tenant duplicada em {table}")


def _has_named_index(bind, name: str) -> bool:
    return bool(bind.execute(sa.text("""
        SELECT 1 FROM pg_class index_rel
        JOIN pg_namespace ns ON ns.oid = index_rel.relnamespace
        WHERE ns.nspname = current_schema() AND index_rel.relname = :name LIMIT 1
    """), {"name": name}).scalar())


def _ensure_scoped_unique(bind, name: str, table: str, columns: str, where: str | None) -> None:
    if not _has_named_index(bind, name):
        clause = f" WHERE {where}" if where else ""
        op.execute(sa.text(f"CREATE UNIQUE INDEX {name} ON {table} ({columns}){clause}"))


def _has_tenant_fk(bind, table: str) -> bool:
    return bool(bind.execute(sa.text("""
        SELECT 1 FROM pg_constraint con
        JOIN pg_class child ON child.oid = con.conrelid
        JOIN pg_class parent ON parent.oid = con.confrelid
        JOIN pg_namespace ns ON ns.oid = child.relnamespace
        WHERE ns.nspname = current_schema() AND con.contype = 'f'
          AND child.relname = :table AND parent.relname = 'tenants'
          AND pg_get_constraintdef(con.oid) ILIKE '%FOREIGN KEY (tenant_id)%'
        LIMIT 1
    """), {"table": table}).scalar())


def _has_composite_fk(bind, table: str, column: str, parent: str) -> bool:
    return bool(bind.execute(sa.text("""
        SELECT 1 FROM pg_constraint con
        JOIN pg_class child ON child.oid = con.conrelid
        JOIN pg_class parent_rel ON parent_rel.oid = con.confrelid
        JOIN pg_namespace ns ON ns.oid = child.relnamespace
        WHERE ns.nspname = current_schema() AND con.contype = 'f'
          AND child.relname = :table AND parent_rel.relname = :parent
          AND pg_get_constraintdef(con.oid) ILIKE :signature LIMIT 1
    """), {"table": table, "parent": parent,
           "signature": f"%FOREIGN KEY (tenant_id, {column}) REFERENCES {parent} (tenant_id, id)%"}).scalar())


def _validate_tenant_constraints(bind, table: str) -> None:
    names = bind.execute(sa.text("""
        SELECT con.conname FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace ns ON ns.oid = rel.relnamespace
        WHERE ns.nspname = current_schema() AND rel.relname = :table
          AND con.contype = 'f' AND NOT con.convalidated
          AND pg_get_constraintdef(con.oid) ILIKE '%FOREIGN KEY (tenant_id%'
    """), {"table": table}).scalars().all()
    for name in names:
        op.execute(sa.text(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{name}"'))


def _drop_legacy_single_column_unique(bind, table: str, column: str) -> None:
    """Drop only table-wide UNIQUE(column), never a tenant-scoped index."""
    constraints = bind.execute(sa.text("""
        SELECT con.conname FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace ns ON ns.oid = rel.relnamespace
        WHERE ns.nspname = current_schema() AND rel.relname = :table
          AND con.contype = 'u' AND pg_get_constraintdef(con.oid) = :definition
    """), {"table": table, "definition": f"UNIQUE ({column})"}).scalars().all()
    for name in constraints:
        op.drop_constraint(name, table, type_="unique")
    indexes = bind.execute(sa.text("""
        SELECT index_rel.relname FROM pg_index idx
        JOIN pg_class table_rel ON table_rel.oid = idx.indrelid
        JOIN pg_class index_rel ON index_rel.oid = idx.indexrelid
        JOIN pg_namespace ns ON ns.oid = table_rel.relnamespace
        WHERE ns.nspname = current_schema() AND table_rel.relname = :table
          AND idx.indisunique AND NOT idx.indisprimary AND idx.indnkeyatts = 1
          AND pg_get_indexdef(idx.indexrelid) ILIKE :signature
    """), {"table": table, "signature": f"%({column})%"}).scalars().all()
    for name in indexes:
        op.drop_index(name, table_name=table)


def upgrade() -> None:
    bind = op.get_bind()
    for table in LOGISTICS_TABLES + ("freight_type_configs",):
        if _invalid_ownership(bind, table):
            raise RuntimeError(f"Wave 7 logistica: tenant ownership invalido em {table}")
    _assert_same_tenant_references(bind)
    for _name, table, expression, where in SCOPED_UNIQUES:
        _assert_scoped_unique_rows(bind, table, expression, where)

    for table in LOGISTICS_TABLES:
        if not _has_tenant_fk(bind, table):
            op.execute(sa.text(
                f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_tenant_id_tenants "
                "FOREIGN KEY (tenant_id) REFERENCES tenants(id) NOT VALID"
            ))
    for child, column, parent, ondelete in OWNERSHIP_PAIRS:
        if not _has_composite_fk(bind, child, column, parent):
            delete = " ON DELETE CASCADE" if ondelete == "CASCADE" else ""
            op.execute(sa.text(
                f"ALTER TABLE {child} ADD CONSTRAINT fk_wave7_{child}_{column} "
                f"FOREIGN KEY (tenant_id, {column}) REFERENCES {parent} (tenant_id, id){delete} NOT VALID"
            ))
    for table in LOGISTICS_TABLES:
        _validate_tenant_constraints(bind, table)
        op.alter_column(table, "tenant_id", existing_type=sa.String(), nullable=False, server_default=None)

    for name, table, columns, where in SCOPED_UNIQUES:
        _ensure_scoped_unique(bind, name, table, columns, where)
    _drop_legacy_single_column_unique(bind, "deliveries", "order_id")
    _drop_legacy_single_column_unique(bind, "delivery_persons", "email")
    _drop_legacy_single_column_unique(bind, "freight_type_configs", "freight_type")


def downgrade() -> None:
    # Reintroducing global identities or nullable ownership is unsafe.
    pass
