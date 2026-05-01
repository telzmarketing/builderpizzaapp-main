"""product variation promotions

Revision ID: 20260425_product_promotions
Revises: 20260424_pizza_size_descriptions
Create Date: 2026-04-25
"""
from __future__ import annotations

from alembic import op

revision = "20260425_product_promotions"
down_revision = "20260424_pizza_size_descriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS product_promotions (
            id VARCHAR PRIMARY KEY,
            product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            valid_weekdays TEXT NOT NULL DEFAULT '[]',
            start_time VARCHAR(5),
            end_time VARCHAR(5),
            start_date DATE,
            end_date DATE,
            discount_type VARCHAR(30) NOT NULL DEFAULT 'fixed_price',
            default_value FLOAT,
            timezone VARCHAR(80) NOT NULL DEFAULT 'America/Sao_Paulo',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_product_promotions_product_id ON product_promotions(product_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS product_promotion_combinations (
            id VARCHAR PRIMARY KEY,
            promotion_id VARCHAR NOT NULL REFERENCES product_promotions(id) ON DELETE CASCADE,
            product_size_id VARCHAR REFERENCES product_sizes(id) ON DELETE CASCADE,
            product_crust_type_id VARCHAR REFERENCES product_crust_types(id) ON DELETE CASCADE,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            promotional_value FLOAT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_product_promotion_combination UNIQUE (
                promotion_id,
                product_size_id,
                product_crust_type_id
            )
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_product_promotion_combinations_promotion_id ON product_promotion_combinations(promotion_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_product_promotion_combinations_product_size_id ON product_promotion_combinations(product_size_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_product_promotion_combinations_product_crust_type_id ON product_promotion_combinations(product_crust_type_id)")

    op.execute("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS selected_size_id VARCHAR")
    op.execute("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS selected_crust_type_id VARCHAR")
    op.execute("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS flavor_count INTEGER DEFAULT 1")
    op.execute("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS standard_unit_price FLOAT")
    op.execute("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS applied_unit_price FLOAT")
    op.execute("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS promotion_id VARCHAR")
    op.execute("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS promotion_name VARCHAR(200)")
    op.execute("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS promotion_discount FLOAT DEFAULT 0")
    op.execute("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS promotion_blocked BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS promotion_block_reason VARCHAR(300)")


def downgrade() -> None:
    op.drop_column("order_items", "promotion_block_reason")
    op.drop_column("order_items", "promotion_blocked")
    op.drop_column("order_items", "promotion_discount")
    op.drop_column("order_items", "promotion_name")
    op.drop_column("order_items", "promotion_id")
    op.drop_column("order_items", "applied_unit_price")
    op.drop_column("order_items", "standard_unit_price")
    op.drop_column("order_items", "flavor_count")
    op.drop_column("order_items", "selected_crust_type_id")
    op.drop_column("order_items", "selected_size_id")
    op.drop_table("product_promotion_combinations")
    op.drop_table("product_promotions")
