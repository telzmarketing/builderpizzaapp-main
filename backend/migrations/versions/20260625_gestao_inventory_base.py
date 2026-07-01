"""gestao inventory base

Revision ID: 20260625_gestao_inventory_base
Revises: 20260625_gestao_phase1_base
"""
from __future__ import annotations

from alembic import op

revision = "20260625_gestao_inventory_base"
down_revision = "20260625_gestao_phase1_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory_units (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            name VARCHAR(120) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            unit_type VARCHAR(30) NOT NULL DEFAULT 'unit',
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_units_tenant_id ON inventory_units(tenant_id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_units_tenant_name ON inventory_units(tenant_id, lower(name))")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory_categories (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            name VARCHAR(140) NOT NULL,
            description TEXT,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_categories_tenant_id ON inventory_categories(tenant_id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_categories_tenant_name ON inventory_categories(tenant_id, lower(name))")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory_locations (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            name VARCHAR(140) NOT NULL,
            description TEXT,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_locations_tenant_id ON inventory_locations(tenant_id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_locations_tenant_name ON inventory_locations(tenant_id, lower(name))")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory_suppliers (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            name VARCHAR(180) NOT NULL,
            document VARCHAR(60),
            phone VARCHAR(60),
            email VARCHAR(180),
            notes TEXT,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_suppliers_tenant_id ON inventory_suppliers(tenant_id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_suppliers_tenant_name ON inventory_suppliers(tenant_id, lower(name))")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory_items (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            name VARCHAR(180) NOT NULL,
            sku VARCHAR(80),
            item_type VARCHAR(40) NOT NULL DEFAULT 'ingredient',
            category_id VARCHAR REFERENCES inventory_categories(id) ON DELETE SET NULL,
            unit_id VARCHAR REFERENCES inventory_units(id) ON DELETE SET NULL,
            default_location_id VARCHAR REFERENCES inventory_locations(id) ON DELETE SET NULL,
            min_stock FLOAT NOT NULL DEFAULT 0,
            notes TEXT,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_items_tenant_id ON inventory_items(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_items_sku ON inventory_items(sku)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_items_category_id ON inventory_items(category_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_items_unit_id ON inventory_items(unit_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_items_default_location_id ON inventory_items(default_location_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory_purchases (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            supplier_id VARCHAR REFERENCES inventory_suppliers(id) ON DELETE SET NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'draft',
            invoice_number VARCHAR(80),
            expected_date DATE,
            notes TEXT,
            total_amount FLOAT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_purchases_tenant_id ON inventory_purchases(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_purchases_supplier_id ON inventory_purchases(supplier_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_purchases_status ON inventory_purchases(status)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory_purchase_items (
            id VARCHAR PRIMARY KEY,
            purchase_id VARCHAR NOT NULL REFERENCES inventory_purchases(id) ON DELETE CASCADE,
            item_id VARCHAR NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
            quantity FLOAT NOT NULL DEFAULT 0,
            unit_cost FLOAT NOT NULL DEFAULT 0,
            total_cost FLOAT NOT NULL DEFAULT 0
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_purchase_items_purchase_id ON inventory_purchase_items(purchase_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_purchase_items_item_id ON inventory_purchase_items(item_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory_manual_entries (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            item_id VARCHAR NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
            location_id VARCHAR REFERENCES inventory_locations(id) ON DELETE SET NULL,
            quantity FLOAT NOT NULL DEFAULT 0,
            unit_cost FLOAT NOT NULL DEFAULT 0,
            reason VARCHAR(120) NOT NULL DEFAULT 'initial_stock',
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_manual_entries_tenant_id ON inventory_manual_entries(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_manual_entries_item_id ON inventory_manual_entries(item_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_manual_entries_location_id ON inventory_manual_entries(location_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS inventory_manual_entries")
    op.execute("DROP TABLE IF EXISTS inventory_purchase_items")
    op.execute("DROP TABLE IF EXISTS inventory_purchases")
    op.execute("DROP TABLE IF EXISTS inventory_items")
    op.execute("DROP TABLE IF EXISTS inventory_suppliers")
    op.execute("DROP TABLE IF EXISTS inventory_locations")
    op.execute("DROP TABLE IF EXISTS inventory_categories")
    op.execute("DROP TABLE IF EXISTS inventory_units")
