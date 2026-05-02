"""customer crm metrics

Revision ID: 20260501_customer_crm_metrics
Revises: 20260501_chatbot_modes
Create Date: 2026-05-01
"""
from __future__ import annotations

from alembic import op

revision = "20260501_customer_crm_metrics"
down_revision = "20260501_chatbot_modes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS birth_date DATE")
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS first_order_at TIMESTAMPTZ")
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS last_order_at TIMESTAMPTZ")
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS total_orders INTEGER DEFAULT 0")
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS total_spent FLOAT DEFAULT 0.0")
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS avg_ticket FLOAT DEFAULT 0.0")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customers_last_order_at ON customers(last_order_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customers_total_spent ON customers(total_spent DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customers_avg_ticket ON customers(avg_ticket DESC)")

    op.execute(
        """
        WITH stats AS (
            SELECT
                customer_id,
                COUNT(*)::INTEGER AS total_orders,
                COALESCE(SUM(total), 0.0) AS total_spent,
                MIN(created_at) AS first_order_at,
                MAX(created_at) AS last_order_at
            FROM orders
            WHERE customer_id IS NOT NULL
              AND status::TEXT IN ('paid', 'pago', 'preparing', 'ready_for_pickup', 'on_the_way', 'delivered')
            GROUP BY customer_id
        )
        UPDATE customers c
        SET
            total_orders = stats.total_orders,
            total_spent = ROUND(stats.total_spent::numeric, 2)::float,
            avg_ticket = CASE
                WHEN stats.total_orders > 0 THEN ROUND((stats.total_spent / stats.total_orders)::numeric, 2)::float
                ELSE 0.0
            END,
            first_order_at = stats.first_order_at,
            last_order_at = stats.last_order_at
        FROM stats
        WHERE c.id = stats.customer_id
        """
    )
    op.execute(
        """
        UPDATE customers c
        SET total_orders = 0, total_spent = 0.0, avg_ticket = 0.0,
            first_order_at = NULL, last_order_at = NULL
        WHERE NOT EXISTS (
            SELECT 1
            FROM orders o
            WHERE o.customer_id = c.id
              AND o.status::TEXT IN ('paid', 'pago', 'preparing', 'ready_for_pickup', 'on_the_way', 'delivered')
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_customers_avg_ticket")
    op.execute("DROP INDEX IF EXISTS ix_customers_total_spent")
    op.execute("DROP INDEX IF EXISTS ix_customers_last_order_at")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS avg_ticket")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS total_spent")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS total_orders")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS last_order_at")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS first_order_at")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS birth_date")
