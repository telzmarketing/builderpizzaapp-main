"""Persist the operator discount snapshot on manual orders."""

from alembic import op


revision = "20261117_manual_order_discounts"
down_revision = "20261117_home_promotions_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS manual_discount_type VARCHAR(20)")
    op.execute("ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS manual_discount_value DOUBLE PRECISION")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_orders_manual_discount_type'
            ) THEN
                ALTER TABLE orders ADD CONSTRAINT ck_orders_manual_discount_type
                    CHECK (manual_discount_type IS NULL OR manual_discount_type IN ('percentage', 'fixed'));
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS orders DROP CONSTRAINT IF EXISTS ck_orders_manual_discount_type")
    op.execute("ALTER TABLE IF EXISTS orders DROP COLUMN IF EXISTS manual_discount_value")
    op.execute("ALTER TABLE IF EXISTS orders DROP COLUMN IF EXISTS manual_discount_type")
