"""Decimal inventory and tenant-owned operation, packaging, lot and reservation foundations.

Forward only. No synthetic lot/expiry backfill. Preflight rejects nonfinite,
overflowing or over-scale historical values rather than silently rounding.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261021_inventory_foundation"
down_revision = "20261020_inventory_recipe_fractions"
branch_labels = None
depends_on = None

DECIMAL_COLUMNS = {'inventory_items': {'min_stock': (20, 6)},
 'inventory_purchases': {'total_amount': (20, 8)},
 'inventory_purchase_items': {'quantity': (20, 6), 'unit_cost': (20, 8), 'total_cost': (20, 8)},
 'inventory_manual_entries': {'quantity': (20, 6), 'unit_cost': (20, 8)},
 'inventory_stock_movements': {'quantity_delta': (20, 6), 'unit_cost': (20, 8)},
 'inventory_recipe_versions': {'reference_fraction': (20, 12)},
 'inventory_recipe_items': {'quantity': (20, 6), 'waste_percent': (20, 12)}}


def upgrade():
    # All checks precede any mutation: an operator must reconcile incompatible
    # historical values explicitly on a disposable clone before retrying.
    for table, columns in DECIMAL_COLUMNS.items():
        for column, (precision, scale) in columns.items():
            op.execute(f"""DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM {table} WHERE {column}::text IN ('NaN','Infinity','-Infinity')) THEN
                    RAISE EXCEPTION 'Nonfinite legacy value: {table}.{column}';
                END IF;
                IF EXISTS (SELECT 1 FROM {table} WHERE abs({column}::text::numeric) >= power(10::numeric, {precision - scale}) OR {column}::text::numeric <> round({column}::text::numeric, {scale})) THEN
                    RAISE EXCEPTION 'Legacy value exceeds target precision/scale: {table}.{column}';
                END IF;
            END $$""")
    for table, columns in DECIMAL_COLUMNS.items():
        for column, (precision, scale) in columns.items():
            op.alter_column(table, column, existing_type=sa.Float(), type_=sa.Numeric(precision, scale), existing_nullable=False, postgresql_using=f"{column}::text::numeric({precision},{scale})")
            op.create_check_constraint(f"ck_{table}_{column}_finite", table, f"CAST({column} AS VARCHAR) <> 'NaN'")
    # Enforce tenant-safe new writes without silently rewriting legacy ownership.
    # NOT VALID preserves historical exceptions for a separately authorized reconciliation.
    op.execute("ALTER TABLE inventory_stock_movements ADD CONSTRAINT fk_inventory_movement_tenant_item FOREIGN KEY (tenant_id,item_id) REFERENCES inventory_items(tenant_id,id) ON DELETE RESTRICT NOT VALID")
    op.execute("ALTER TABLE inventory_stock_movements ADD CONSTRAINT fk_inventory_movement_tenant_location FOREIGN KEY (tenant_id,location_id) REFERENCES inventory_locations(tenant_id,id) ON DELETE RESTRICT NOT VALID")
    op.execute("ALTER TABLE inventory_units ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
    op.create_check_constraint("ck_inventory_unit_version", "inventory_units", "version > 0")
    op.execute('ALTER TABLE inventory_units ADD COLUMN code VARCHAR(30)')
    op.execute('ALTER TABLE inventory_units ADD COLUMN dimension VARCHAR(10)')
    op.execute('ALTER TABLE inventory_units ADD COLUMN conversion_factor NUMERIC(24,12)')
    op.execute('CREATE UNIQUE INDEX uq_inventory_units_tenant_code ON inventory_units(tenant_id,code)')
    op.execute("ALTER TABLE inventory_units ADD CONSTRAINT ck_inventory_unit_dimension CHECK (dimension IS NULL OR dimension IN ('mass','volume','count'))")
    op.execute('ALTER TABLE inventory_units ADD CONSTRAINT ck_inventory_unit_classification CHECK ((dimension IS NULL AND conversion_factor IS NULL) OR (dimension IS NOT NULL AND conversion_factor IS NOT NULL))')
    op.execute('ALTER TABLE inventory_units ADD CONSTRAINT ck_inventory_unit_factor CHECK (conversion_factor IS NULL OR conversion_factor > 0)')
    op.execute("""
        CREATE TABLE inventory_operations (
            id VARCHAR NOT NULL, 
            tenant_id VARCHAR NOT NULL, 
            kind VARCHAR(40) NOT NULL, 
            business_key VARCHAR(200) NOT NULL, 
            idempotency_scope VARCHAR(200) NOT NULL, 
            idempotency_key VARCHAR(200) NOT NULL, 
            request_hash VARCHAR(64) NOT NULL, 
            status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
            result_json JSONB, 
            actor_id VARCHAR NOT NULL, 
            version INTEGER DEFAULT '1' NOT NULL, 
            created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
            committed_at TIMESTAMP WITH TIME ZONE, 
            PRIMARY KEY (id), 
            CONSTRAINT ck_inventory_operation_kind CHECK (kind IN ('manual_in','manual_out','transfer','loss','adjustment_in','adjustment_out','order_sale','order_sale_reversal','order_sale_loss','reservation','reservation_release','receipt','preparation','compensation','unit_definition','packaging_definition','lot_definition','lot_state')), 
            CONSTRAINT ck_inventory_operation_status CHECK (status IN ('pending','committed')), 
            CONSTRAINT ck_inventory_operation_version CHECK (version > 0), 
            CONSTRAINT ck_inventory_operation_identity CHECK (length(business_key) > 0 AND length(idempotency_key) > 0 AND length(idempotency_scope) > 0), 
            CONSTRAINT ck_inventory_operation_request_hash CHECK (length(request_hash) = 64), 
            FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE RESTRICT
        )
    """)
    op.execute('CREATE INDEX ix_inventory_operations_tenant_created ON inventory_operations (tenant_id, created_at)')
    op.execute('CREATE UNIQUE INDEX uq_inventory_operation_business ON inventory_operations (tenant_id, kind, business_key)')
    op.execute('CREATE UNIQUE INDEX uq_inventory_operation_request ON inventory_operations (tenant_id, idempotency_scope, idempotency_key)')
    op.execute('CREATE UNIQUE INDEX uq_inventory_operations_tenant_id_id ON inventory_operations (tenant_id, id)')
    op.execute("""
        CREATE TABLE inventory_item_packagings (
            id VARCHAR NOT NULL, 
            tenant_id VARCHAR NOT NULL, 
            item_id VARCHAR NOT NULL, 
            supplier_id VARCHAR, 
            name VARCHAR(180) NOT NULL, 
            commercial_unit_id VARCHAR NOT NULL, 
            base_unit_id VARCHAR NOT NULL, 
            factor NUMERIC(24, 12), 
            variable_weight BOOLEAN DEFAULT 'false' NOT NULL, 
            version INTEGER DEFAULT '1' NOT NULL, 
            active BOOLEAN DEFAULT 'true' NOT NULL, 
            actor_id VARCHAR NOT NULL, 
            created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
            PRIMARY KEY (id), 
            CONSTRAINT fk_inventory_packaging_item FOREIGN KEY(tenant_id, item_id) REFERENCES inventory_items (tenant_id, id) ON DELETE RESTRICT, 
            CONSTRAINT fk_inventory_packaging_supplier FOREIGN KEY(tenant_id, supplier_id) REFERENCES inventory_suppliers (tenant_id, id) ON DELETE RESTRICT, 
            CONSTRAINT fk_inventory_packaging_commercial_unit FOREIGN KEY(tenant_id, commercial_unit_id) REFERENCES inventory_units (tenant_id, id) ON DELETE RESTRICT, 
            CONSTRAINT fk_inventory_packaging_base_unit FOREIGN KEY(tenant_id, base_unit_id) REFERENCES inventory_units (tenant_id, id) ON DELETE RESTRICT, 
            CONSTRAINT ck_inventory_packaging_factor CHECK ((variable_weight AND factor IS NULL) OR (NOT variable_weight AND factor IS NOT NULL AND factor > 0)), 
            CONSTRAINT ck_inventory_packaging_version CHECK (version > 0), 
            FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE RESTRICT, 
            FOREIGN KEY(actor_id) REFERENCES admin_users (id) ON DELETE RESTRICT
        )
    """)
    op.execute('CREATE INDEX ix_inventory_packagings_tenant_item ON inventory_item_packagings (tenant_id, item_id, supplier_id)')
    op.execute('CREATE UNIQUE INDEX uq_inventory_packagings_tenant_id_id ON inventory_item_packagings (tenant_id, id)')
    op.execute("""
        CREATE TABLE inventory_lots (
            id VARCHAR NOT NULL, 
            tenant_id VARCHAR NOT NULL, 
            item_id VARCHAR NOT NULL, 
            location_id VARCHAR NOT NULL, 
            supplier_id VARCHAR, 
            lot_code VARCHAR(120) NOT NULL, 
            received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
            manufactured_on DATE, 
            expires_on DATE, 
            effective_expires_at TIMESTAMP WITH TIME ZONE, 
            status VARCHAR(20) DEFAULT 'available' NOT NULL, 
            version INTEGER DEFAULT '1' NOT NULL, 
            notes TEXT, 
            actor_id VARCHAR NOT NULL, 
            created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
            PRIMARY KEY (id), 
            CONSTRAINT fk_inventory_lot_item FOREIGN KEY(tenant_id, item_id) REFERENCES inventory_items (tenant_id, id) ON DELETE RESTRICT, 
            CONSTRAINT fk_inventory_lot_location FOREIGN KEY(tenant_id, location_id) REFERENCES inventory_locations (tenant_id, id) ON DELETE RESTRICT, 
            CONSTRAINT fk_inventory_lot_supplier FOREIGN KEY(tenant_id, supplier_id) REFERENCES inventory_suppliers (tenant_id, id) ON DELETE RESTRICT, 
            CONSTRAINT ck_inventory_lot_status CHECK (status IN ('available','blocked','quarantine','consumed','discarded')), 
            CONSTRAINT ck_inventory_lot_identity CHECK (version > 0 AND length(trim(lot_code)) > 0), 
            CONSTRAINT ck_inventory_lot_dates CHECK (manufactured_on IS NULL OR expires_on IS NULL OR manufactured_on <= expires_on), 
            FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE RESTRICT, 
            FOREIGN KEY(actor_id) REFERENCES admin_users (id) ON DELETE RESTRICT
        )
    """)
    op.execute('CREATE INDEX ix_inventory_lots_fefo ON inventory_lots (tenant_id, item_id, status, effective_expires_at, received_at, id)')
    op.execute('CREATE UNIQUE INDEX uq_inventory_lots_tenant_id_id ON inventory_lots (tenant_id, id)')
    op.execute('CREATE UNIQUE INDEX uq_inventory_lots_tenant_id_item ON inventory_lots (tenant_id, id, item_id)')
    op.execute("""
        CREATE TABLE inventory_reservations (
            id VARCHAR NOT NULL, 
            tenant_id VARCHAR NOT NULL, 
            business_key VARCHAR(200) NOT NULL, 
            item_id VARCHAR NOT NULL, 
            location_id VARCHAR NOT NULL, 
            lot_id VARCHAR, 
            operation_id VARCHAR, 
            source_type VARCHAR(40) NOT NULL, 
            source_id VARCHAR(200) NOT NULL, 
            quantity NUMERIC(20, 6) NOT NULL, 
            status VARCHAR(20) DEFAULT 'active' NOT NULL, 
            expires_at TIMESTAMP WITH TIME ZONE, 
            version INTEGER DEFAULT '1' NOT NULL, 
            actor_id VARCHAR NOT NULL, 
            created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
            PRIMARY KEY (id), 
            CONSTRAINT fk_inventory_reservation_item FOREIGN KEY(tenant_id, item_id) REFERENCES inventory_items (tenant_id, id) ON DELETE RESTRICT, 
            CONSTRAINT fk_inventory_reservation_lot_item FOREIGN KEY(tenant_id, lot_id, item_id) REFERENCES inventory_lots (tenant_id, id, item_id) ON DELETE RESTRICT, 
            CONSTRAINT fk_inventory_reservation_operation FOREIGN KEY(tenant_id, operation_id) REFERENCES inventory_operations (tenant_id, id) ON DELETE RESTRICT, 
            CONSTRAINT fk_inventory_reservation_location FOREIGN KEY(tenant_id, location_id) REFERENCES inventory_locations (tenant_id, id) ON DELETE RESTRICT, 
            CONSTRAINT ck_inventory_reservation_quantity CHECK (quantity > 0 AND version > 0), 
            CONSTRAINT ck_inventory_reservation_status CHECK (status IN ('active','consumed','released','expired')), 
            CONSTRAINT ck_inventory_reservation_identity CHECK (length(business_key) > 0 AND length(source_type) > 0 AND length(source_id) > 0), 
            FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE RESTRICT, 
            FOREIGN KEY(actor_id) REFERENCES admin_users (id) ON DELETE RESTRICT
        )
    """)
    op.execute('CREATE INDEX ix_inventory_reservations_active ON inventory_reservations (tenant_id, item_id, status, expires_at)')
    op.execute('CREATE UNIQUE INDEX uq_inventory_reservation_business ON inventory_reservations (tenant_id, business_key)')
    op.execute('CREATE UNIQUE INDEX uq_inventory_reservations_tenant_id_id ON inventory_reservations (tenant_id, id)')
    op.execute('ALTER TABLE inventory_stock_movements ADD COLUMN operation_id VARCHAR')
    op.execute('ALTER TABLE inventory_stock_movements ADD COLUMN operation_sequence INTEGER')
    op.execute('ALTER TABLE inventory_stock_movements ADD COLUMN logical_line_id VARCHAR')
    op.execute('ALTER TABLE inventory_stock_movements ADD COLUMN lot_id VARCHAR')
    op.execute('ALTER TABLE inventory_stock_movements ADD CONSTRAINT ck_inventory_movement_lot_operation CHECK (lot_id IS NULL OR (tenant_id IS NOT NULL AND operation_id IS NOT NULL))')
    op.execute('ALTER TABLE inventory_stock_movements ADD CONSTRAINT ck_inventory_movement_operation CHECK ((operation_id IS NULL AND operation_sequence IS NULL) OR (operation_id IS NOT NULL AND operation_sequence IS NOT NULL AND operation_sequence > 0 AND tenant_id IS NOT NULL))')
    op.execute('ALTER TABLE inventory_stock_movements ADD CONSTRAINT fk_inventory_movement_lot_item FOREIGN KEY(tenant_id, lot_id, item_id) REFERENCES inventory_lots (tenant_id, id, item_id) ON DELETE RESTRICT')
    op.execute('ALTER TABLE inventory_stock_movements ADD CONSTRAINT fk_inventory_movement_operation FOREIGN KEY(tenant_id, operation_id) REFERENCES inventory_operations (tenant_id, id) ON DELETE RESTRICT')
    op.execute('CREATE INDEX ix_inventory_stock_movements_lot_id ON inventory_stock_movements (lot_id)')
    op.execute('CREATE UNIQUE INDEX uq_inventory_movement_operation_sequence ON inventory_stock_movements (tenant_id, operation_id, operation_sequence)')

    op.create_check_constraint("ck_inventory_units_conversion_factor_finite", "inventory_units", "CAST(conversion_factor AS VARCHAR) <> 'NaN'")
    op.create_check_constraint("ck_inventory_item_packagings_factor_finite", "inventory_item_packagings", "CAST(factor AS VARCHAR) <> 'NaN'")
    op.create_check_constraint("ck_inventory_reservations_quantity_finite", "inventory_reservations", "CAST(quantity AS VARCHAR) <> 'NaN'")


def downgrade():
    raise RuntimeError("Forward-only: preserve decimal quantities, operation identities and stock traceability.")
