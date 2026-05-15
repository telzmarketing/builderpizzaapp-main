"""product promotion benefits

Revision ID: 20260515_product_promotion_benefits
Revises: 20260515_visitor_neighborhood_bi
Create Date: 2026-05-15
"""

from alembic import op


revision = "20260515_product_promotion_benefits"
down_revision = "20260515_visitor_neighborhood_bi"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE product_promotions ADD COLUMN IF NOT EXISTS free_shipping BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE product_promotions ADD COLUMN IF NOT EXISTS gift_enabled BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE product_promotions ADD COLUMN IF NOT EXISTS gift_product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE product_promotions ADD COLUMN IF NOT EXISTS gift_quantity INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE product_promotions ADD COLUMN IF NOT EXISTS blocks_other_coupons BOOLEAN NOT NULL DEFAULT FALSE")


def downgrade() -> None:
    op.execute("ALTER TABLE product_promotions DROP COLUMN IF EXISTS blocks_other_coupons")
    op.execute("ALTER TABLE product_promotions DROP COLUMN IF EXISTS gift_quantity")
    op.execute("ALTER TABLE product_promotions DROP COLUMN IF EXISTS gift_product_id")
    op.execute("ALTER TABLE product_promotions DROP COLUMN IF EXISTS gift_enabled")
    op.execute("ALTER TABLE product_promotions DROP COLUMN IF EXISTS free_shipping")
