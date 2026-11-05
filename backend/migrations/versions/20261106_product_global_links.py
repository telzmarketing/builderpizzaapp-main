"""Add optional global catalog links to legacy product options.

This is an expand-only revision. Existing option IDs, names and persisted prices
remain untouched; links are nullable so old tenants and rows stay readable.
"""

from alembic import op
import sqlalchemy as sa


revision = "20261106_product_global_links"
down_revision = "20261106_global_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_sizes", sa.Column("global_size_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_product_sizes_global_size",
        "product_sizes",
        "pizza_global_sizes",
        ["global_size_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_product_sizes_global_size_id", "product_sizes", ["global_size_id"])
    op.create_unique_constraint(
        "uq_product_sizes_product_global_size",
        "product_sizes",
        ["tenant_id", "product_id", "global_size_id"],
    )

    op.add_column("product_crust_types", sa.Column("global_dough_type_id", sa.String(36), nullable=True))
    op.add_column("product_crust_types", sa.Column("global_crust_id", sa.String(36), nullable=True))
    op.add_column("product_crust_types", sa.Column("price_addition_override", sa.Float(), nullable=True))
    op.create_foreign_key(
        "fk_product_crust_global_dough",
        "product_crust_types",
        "pizza_global_dough_types",
        ["global_dough_type_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_product_crust_global_crust",
        "product_crust_types",
        "pizza_global_crusts",
        ["global_crust_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_product_crust_types_global_dough_type_id", "product_crust_types", ["global_dough_type_id"])
    op.create_index("ix_product_crust_types_global_crust_id", "product_crust_types", ["global_crust_id"])
    op.create_unique_constraint(
        "uq_product_crust_product_global_dough",
        "product_crust_types",
        ["tenant_id", "product_id", "global_dough_type_id"],
    )
    op.create_unique_constraint(
        "uq_product_crust_product_global_crust",
        "product_crust_types",
        ["tenant_id", "product_id", "global_crust_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_product_crust_product_global_crust", "product_crust_types", type_="unique")
    op.drop_constraint("uq_product_crust_product_global_dough", "product_crust_types", type_="unique")
    op.drop_index("ix_product_crust_types_global_crust_id", table_name="product_crust_types")
    op.drop_index("ix_product_crust_types_global_dough_type_id", table_name="product_crust_types")
    op.drop_constraint("fk_product_crust_global_crust", "product_crust_types", type_="foreignkey")
    op.drop_constraint("fk_product_crust_global_dough", "product_crust_types", type_="foreignkey")
    op.drop_column("product_crust_types", "price_addition_override")
    op.drop_column("product_crust_types", "global_crust_id")
    op.drop_column("product_crust_types", "global_dough_type_id")

    op.drop_constraint("uq_product_sizes_product_global_size", "product_sizes", type_="unique")
    op.drop_index("ix_product_sizes_global_size_id", table_name="product_sizes")
    op.drop_constraint("fk_product_sizes_global_size", "product_sizes", type_="foreignkey")
    op.drop_column("product_sizes", "global_size_id")
