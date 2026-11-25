"""Repair additive indexes that are declared by tenant-scoped ORM models."""

from alembic import op


revision = "20261125_schema_index_repairs"
down_revision = "20261125_finance_contracts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_print_order_imports_tenant_id",
        "print_order_imports",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_print_order_imports_tenant_id", table_name="print_order_imports")
