"""Harden named catalog option integrity for esfiha/category rollout.

The product type remains a VARCHAR for backward compatibility. This migration
only adds database checks to the existing product_crust_types contract; order
item snapshots are intentionally untouched.
"""
from alembic import op


revision = "20261029_catalog_product_contract"
down_revision = "20261029_order_operational_archive"
branch_labels = None
depends_on = None


def _add_check_if_missing(name: str, expression: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = 'product_crust_types'
                  AND c.conname = '{name}'
            ) THEN
                ALTER TABLE product_crust_types
                ADD CONSTRAINT {name} CHECK ({expression});
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    _add_check_if_missing("ck_product_crust_types_price_addition", "price_addition >= 0")
    _add_check_if_missing("ck_product_crust_types_sort_order", "sort_order >= 0")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE product_crust_types "
        "DROP CONSTRAINT IF EXISTS ck_product_crust_types_sort_order"
    )
    op.execute(
        "ALTER TABLE product_crust_types "
        "DROP CONSTRAINT IF EXISTS ck_product_crust_types_price_addition"
    )
