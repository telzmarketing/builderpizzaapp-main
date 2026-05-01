"""product subcategories

Revision ID: 20260425_product_subcategories
Revises: 20260425_store_operation
Create Date: 2026-04-25
"""
from __future__ import annotations

from alembic import op

revision = "20260425_product_subcategories"
down_revision = "20260425_store_operation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS subcategory VARCHAR(100)")
    op.execute("ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS parent_id VARCHAR")
    op.execute("CREATE INDEX IF NOT EXISTS ix_product_categories_parent_id ON product_categories(parent_id)")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_product_categories_parent_id'
            ) THEN
                ALTER TABLE product_categories
                ADD CONSTRAINT fk_product_categories_parent_id
                FOREIGN KEY (parent_id)
                REFERENCES product_categories(id)
                ON DELETE CASCADE;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_product_categories_parent_id", "product_categories", type_="foreignkey")
    op.drop_index("ix_product_categories_parent_id", table_name="product_categories")
    op.drop_column("product_categories", "parent_id")
    op.drop_column("products", "subcategory")
