"""product subcategories

Revision ID: 20260425_product_subcategories
Revises: 20260425_store_operation
Create Date: 2026-04-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260425_product_subcategories"
down_revision = "20260425_store_operation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("subcategory", sa.String(length=100), nullable=True))
    op.add_column("product_categories", sa.Column("parent_id", sa.String(), nullable=True))
    op.create_index("ix_product_categories_parent_id", "product_categories", ["parent_id"])
    op.create_foreign_key(
        "fk_product_categories_parent_id",
        "product_categories",
        "product_categories",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_product_categories_parent_id", "product_categories", type_="foreignkey")
    op.drop_index("ix_product_categories_parent_id", table_name="product_categories")
    op.drop_column("product_categories", "parent_id")
    op.drop_column("products", "subcategory")
