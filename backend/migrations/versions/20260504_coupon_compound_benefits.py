"""coupon compound benefits

Revision ID: 20260504_coupon_compound_benefits
Revises: 20260504_customer_password_auth
Create Date: 2026-05-04
"""
from __future__ import annotations

from alembic import op

revision = "20260504_coupon_compound_benefits"
down_revision = "20260504_customer_password_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS coupons ADD COLUMN IF NOT EXISTS starts_at TIMESTAMPTZ")
    op.execute("ALTER TABLE IF EXISTS coupons ADD COLUMN IF NOT EXISTS ends_at TIMESTAMPTZ")
    op.execute("ALTER TABLE IF EXISTS coupons ADD COLUMN IF NOT EXISTS free_shipping BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE IF EXISTS coupons ADD COLUMN IF NOT EXISTS gift_enabled BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE IF EXISTS coupons ADD COLUMN IF NOT EXISTS gift_product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE IF EXISTS coupons ADD COLUMN IF NOT EXISTS gift_quantity INTEGER DEFAULT 1")
    op.execute("ALTER TABLE IF EXISTS coupons ADD COLUMN IF NOT EXISTS stackable BOOLEAN DEFAULT FALSE")

    op.execute("ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS delivery_fee_original FLOAT DEFAULT 0")
    op.execute("ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS delivery_fee_discount FLOAT DEFAULT 0")
    op.execute("ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS delivery_fee_final FLOAT DEFAULT 0")
    op.execute("ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS free_shipping_applied BOOLEAN DEFAULT FALSE")

    op.execute("ALTER TABLE IF EXISTS order_items ADD COLUMN IF NOT EXISTS original_price FLOAT")
    op.execute("ALTER TABLE IF EXISTS order_items ADD COLUMN IF NOT EXISTS is_gift BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE IF EXISTS order_items ADD COLUMN IF NOT EXISTS gift_reason VARCHAR(100)")
    op.execute("ALTER TABLE IF EXISTS order_items ADD COLUMN IF NOT EXISTS coupon_id VARCHAR")
    op.execute("ALTER TABLE IF EXISTS order_items ADD COLUMN IF NOT EXISTS coupon_code VARCHAR(50)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_items_is_gift ON order_items(is_gift)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_items_coupon_id ON order_items(coupon_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_order_items_coupon_id")
    op.execute("DROP INDEX IF EXISTS ix_order_items_is_gift")
    op.execute("ALTER TABLE IF EXISTS order_items DROP COLUMN IF EXISTS coupon_code")
    op.execute("ALTER TABLE IF EXISTS order_items DROP COLUMN IF EXISTS coupon_id")
    op.execute("ALTER TABLE IF EXISTS order_items DROP COLUMN IF EXISTS gift_reason")
    op.execute("ALTER TABLE IF EXISTS order_items DROP COLUMN IF EXISTS is_gift")
    op.execute("ALTER TABLE IF EXISTS order_items DROP COLUMN IF EXISTS original_price")
    op.execute("ALTER TABLE IF EXISTS orders DROP COLUMN IF EXISTS free_shipping_applied")
    op.execute("ALTER TABLE IF EXISTS orders DROP COLUMN IF EXISTS delivery_fee_final")
    op.execute("ALTER TABLE IF EXISTS orders DROP COLUMN IF EXISTS delivery_fee_discount")
    op.execute("ALTER TABLE IF EXISTS orders DROP COLUMN IF EXISTS delivery_fee_original")
    op.execute("ALTER TABLE IF EXISTS coupons DROP COLUMN IF EXISTS stackable")
    op.execute("ALTER TABLE IF EXISTS coupons DROP COLUMN IF EXISTS gift_quantity")
    op.execute("ALTER TABLE IF EXISTS coupons DROP COLUMN IF EXISTS gift_product_id")
    op.execute("ALTER TABLE IF EXISTS coupons DROP COLUMN IF EXISTS gift_enabled")
    op.execute("ALTER TABLE IF EXISTS coupons DROP COLUMN IF EXISTS free_shipping")
    op.execute("ALTER TABLE IF EXISTS coupons DROP COLUMN IF EXISTS ends_at")
    op.execute("ALTER TABLE IF EXISTS coupons DROP COLUMN IF EXISTS starts_at")
