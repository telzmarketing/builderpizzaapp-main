"""Add salao reservations foundation.

Revision ID: 20260520_salao_reservas_foundation
Revises: 20260519_promotion_landing_media_order
Create Date: 2026-05-20
"""

from alembic import op


revision = "20260520_salao_reservas_foundation"
down_revision = "20260519_promotion_landing_media_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS restaurant_tables (
            id VARCHAR PRIMARY KEY,
            number VARCHAR(30) NOT NULL UNIQUE,
            name VARCHAR(120),
            capacity INTEGER NOT NULL DEFAULT 2,
            location VARCHAR(120),
            status VARCHAR(30) NOT NULL DEFAULT 'available',
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_restaurant_tables_number ON restaurant_tables(number)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_restaurant_tables_status ON restaurant_tables(status)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS reservations (
            id VARCHAR PRIMARY KEY,
            customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
            customer_name VARCHAR(200) NOT NULL,
            customer_phone VARCHAR(40) NOT NULL,
            customer_email VARCHAR(200),
            table_id VARCHAR REFERENCES restaurant_tables(id) ON DELETE SET NULL,
            reservation_date DATE NOT NULL,
            reservation_time TIME NOT NULL,
            guests_count INTEGER NOT NULL DEFAULT 2,
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            notes TEXT,
            source VARCHAR(40) NOT NULL DEFAULT 'salao',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_reservations_customer_id ON reservations(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reservations_table_id ON reservations(table_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reservations_date_status ON reservations(reservation_date, status)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS table_sessions (
            id VARCHAR PRIMARY KEY,
            table_id VARCHAR NOT NULL REFERENCES restaurant_tables(id) ON DELETE RESTRICT,
            customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
            opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            closed_at TIMESTAMPTZ,
            status VARCHAR(30) NOT NULL DEFAULT 'open',
            subtotal FLOAT NOT NULL DEFAULT 0,
            service_fee FLOAT NOT NULL DEFAULT 0,
            discount FLOAT NOT NULL DEFAULT 0,
            total FLOAT NOT NULL DEFAULT 0,
            waiter_name VARCHAR(120),
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_table_sessions_table_id ON table_sessions(table_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_table_sessions_customer_id ON table_sessions(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_table_sessions_status ON table_sessions(status)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS table_session_items (
            id VARCHAR PRIMARY KEY,
            table_session_id VARCHAR NOT NULL REFERENCES table_sessions(id) ON DELETE CASCADE,
            product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
            product_name VARCHAR(200) NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_price FLOAT NOT NULL DEFAULT 0,
            total_price FLOAT NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_table_session_items_table_session_id ON table_session_items(table_session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_table_session_items_product_id ON table_session_items(product_id)")

    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS sales_channel VARCHAR(30) NOT NULL DEFAULT 'delivery'")
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS table_id VARCHAR REFERENCES restaurant_tables(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS table_session_id VARCHAR REFERENCES table_sessions(id) ON DELETE SET NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_sales_channel ON orders(sales_channel)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_table_session_id ON orders(table_session_id)")

    op.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS visible_delivery BOOLEAN NOT NULL DEFAULT TRUE")
    op.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS visible_dine_in BOOLEAN NOT NULL DEFAULT TRUE")
    op.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS delivery_price FLOAT")
    op.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS dine_in_price FLOAT")


def downgrade() -> None:
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS dine_in_price")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS delivery_price")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS visible_dine_in")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS visible_delivery")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS table_session_id")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS table_id")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS sales_channel")
    op.execute("DROP TABLE IF EXISTS table_session_items")
    op.execute("DROP TABLE IF EXISTS table_sessions")
    op.execute("DROP TABLE IF EXISTS reservations")
    op.execute("DROP TABLE IF EXISTS restaurant_tables")
