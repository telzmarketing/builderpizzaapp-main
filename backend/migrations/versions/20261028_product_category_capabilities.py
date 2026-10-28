"""Add tenant-safe category capabilities and product category references.

The migration is additive. Legacy text classifications remain in place, and
IDs/capabilities are backfilled only when the category match is unambiguous
within the existing tenant boundary. Existing related rows are never deleted.
"""
from alembic import op
import sqlalchemy as sa


revision = "20261028_product_category_capabilities"
down_revision = "20261028_order_item_option_selections"
branch_labels = None
depends_on = None


CAPABILITIES = (
    "enable_sizes",
    "enable_product_options",
    "enable_recipe",
    "enable_dough",
    "enable_border",
    "enable_promotions",
)


def upgrade() -> None:
    for column in CAPABILITIES:
        op.add_column(
            "product_categories",
            sa.Column(column, sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    op.add_column("products", sa.Column("category_id", sa.String(), nullable=True))
    op.add_column("products", sa.Column("subcategory_id", sa.String(), nullable=True))
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_subcategory_id", "products", ["subcategory_id"])
    op.create_foreign_key(
        "fk_products_category_id_product_categories",
        "products",
        "product_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_products_subcategory_id_product_categories",
        "products",
        "product_categories",
        ["subcategory_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Resolve the root category first. IS NOT DISTINCT FROM keeps NULL-owned
    # legacy rows isolated from rows belonging to a real tenant.
    op.execute(
        sa.text(
            """
            UPDATE products AS p
            SET category_id = c.id
            FROM product_categories AS c
            WHERE p.category_id IS NULL
              AND p.category IS NOT NULL
              AND c.parent_id IS NULL
              AND lower(trim(c.name)) = lower(trim(p.category))
              AND c.tenant_id IS NOT DISTINCT FROM p.tenant_id
            """
        )
    )
    # If only a legacy subcategory name is available, derive its parent too.
    op.execute(
        sa.text(
            """
            UPDATE products AS p
            SET category_id = c.parent_id
            FROM product_categories AS c
            WHERE p.category_id IS NULL
              AND p.subcategory IS NOT NULL
              AND c.parent_id IS NOT NULL
              AND lower(trim(c.name)) = lower(trim(p.subcategory))
              AND c.tenant_id IS NOT DISTINCT FROM p.tenant_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE products AS p
            SET subcategory_id = c.id
            FROM product_categories AS c
            WHERE p.subcategory_id IS NULL
              AND p.subcategory IS NOT NULL
              AND c.parent_id = p.category_id
              AND lower(trim(c.name)) = lower(trim(p.subcategory))
              AND c.tenant_id IS NOT DISTINCT FROM p.tenant_id
            """
        )
    )

    # Preserve existing catalog behavior where it can be observed safely.
    # Pizza categories get the complete legacy surface; other categories are
    # enabled only for features that already have product data.
    op.execute(
        sa.text(
            """
            UPDATE product_categories AS c
            SET enable_sizes = EXISTS (
                    SELECT 1 FROM products p
                    JOIN product_sizes s ON s.product_id = p.id
                    WHERE p.category_id = c.id OR p.subcategory_id = c.id
                ) OR EXISTS (
                    SELECT 1 FROM products p
                    WHERE (p.category_id = c.id OR p.subcategory_id = c.id)
                      AND p.product_type = 'pizza'
                ),
                enable_product_options = EXISTS (
                    SELECT 1 FROM products p
                    JOIN product_option_groups g ON g.product_id = p.id
                    WHERE p.category_id = c.id OR p.subcategory_id = c.id
                ),
                enable_recipe = EXISTS (
                    SELECT 1 FROM products p
                    JOIN inventory_recipe_versions r ON r.product_id = p.id
                    WHERE p.category_id = c.id OR p.subcategory_id = c.id
                ),
                enable_dough = EXISTS (
                    SELECT 1 FROM products p
                    JOIN product_crust_types ct ON ct.product_id = p.id
                    WHERE (p.category_id = c.id OR p.subcategory_id = c.id)
                      AND coalesce(p.show_crust_options, true)
                ),
                enable_border = EXISTS (
                    SELECT 1 FROM products p
                    JOIN product_crust_types ct ON ct.product_id = p.id
                    WHERE (p.category_id = c.id OR p.subcategory_id = c.id)
                      AND coalesce(p.show_crust_options, true)
                ),
                enable_promotions = EXISTS (
                    SELECT 1 FROM products p
                    JOIN product_promotions pp ON pp.product_id = p.id
                    WHERE p.category_id = c.id OR p.subcategory_id = c.id
                )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE product_categories
            SET enable_sizes = true,
                enable_product_options = true,
                enable_recipe = true,
                enable_dough = true,
                enable_border = true,
                enable_promotions = true
            WHERE lower(name) LIKE '%pizza%'
               OR EXISTS (
                    SELECT 1 FROM products p
                    WHERE (p.category_id = product_categories.id OR p.subcategory_id = product_categories.id)
                      AND p.product_type = 'pizza'
                )
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_products_subcategory_id_product_categories", "products", type_="foreignkey")
    op.drop_constraint("fk_products_category_id_product_categories", "products", type_="foreignkey")
    op.drop_index("ix_products_subcategory_id", table_name="products")
    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_column("products", "subcategory_id")
    op.drop_column("products", "category_id")
    for column in reversed(CAPABILITIES):
        op.drop_column("product_categories", column)
