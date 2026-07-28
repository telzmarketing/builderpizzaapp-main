'''Expand nullable tenant ownership for operational RBAC and catalog.'''
from alembic import op
import sqlalchemy as sa

revision = '20260723_tenant_catalog_expand'
down_revision = '20260722_legacy_tenant_seed'
branch_labels = None
depends_on = None

TABLES = (
    'roles', 'role_permissions', 'user_permissions', 'admin_audit_logs',
    'products', 'product_categories', 'product_sizes', 'product_crust_types',
    'product_drink_variants', 'best_seller_config', 'multi_flavors_config',
    'product_promotions', 'product_promotion_combinations', 'promotions',
    'promotion_landing_pages', 'campaigns', 'campaign_products',
    'promotional_kits', 'promotional_kit_items', 'upsells', 'upsell_metrics',
    'upsell_events', 'order_upsells', 'home_catalog_config', 'theme_settings',
)
UNIQUES = (
    ('roles', ('tenant_id', 'name'), 'uq_roles_tenant_name'),
    ('product_categories', ('tenant_id', 'name'), 'uq_product_categories_tenant_name'),
    ('campaigns', ('tenant_id', 'slug'), 'uq_campaigns_tenant_slug'),
    ('promotion_landing_pages', ('tenant_id', 'slug'), 'uq_promotion_landing_pages_tenant_slug'),
    ('upsell_metrics', ('tenant_id', 'upsell_id'), 'uq_upsell_metrics_tenant_upsell'),
)

def _fk(table):
    return f'fk_{table}_tenant_id_tenants'

def _idx(table):
    return f'uq_{table}_tenant_id_id'

def upgrade():
    op.execute("""CREATE TABLE IF NOT EXISTS upsells (
        id VARCHAR PRIMARY KEY, internal_name VARCHAR(200) NOT NULL,
        product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        image_url TEXT, main_text VARCHAR(500) NOT NULL, secondary_text VARCHAR(500),
        promotional_price FLOAT, trigger_type VARCHAR(50) NOT NULL DEFAULT 'min_value',
        trigger_product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL,
        trigger_category VARCHAR(100), trigger_min_value FLOAT DEFAULT 0,
        trigger_min_quantity INTEGER DEFAULT 1, allowed_weekdays VARCHAR(20) DEFAULT '0123456',
        start_time VARCHAR(5), end_time VARCHAR(5), priority INTEGER NOT NULL DEFAULT 0,
        display_limit INTEGER NOT NULL DEFAULT 1, active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_upsells_active ON upsells(active)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_upsells_priority ON upsells(priority DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_upsells_product_id ON upsells(product_id)")
    op.execute("""CREATE TABLE IF NOT EXISTS upsell_metrics (
        id VARCHAR PRIMARY KEY, upsell_id VARCHAR NOT NULL UNIQUE REFERENCES upsells(id) ON DELETE CASCADE,
        views INTEGER NOT NULL DEFAULT 0, accepts INTEGER NOT NULL DEFAULT 0,
        rejects INTEGER NOT NULL DEFAULT 0, revenue FLOAT NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_upsell_metrics_upsell_id ON upsell_metrics(upsell_id)")
    op.execute("""CREATE TABLE IF NOT EXISTS upsell_events (
        id VARCHAR PRIMARY KEY, upsell_id VARCHAR NOT NULL REFERENCES upsells(id) ON DELETE CASCADE,
        order_id VARCHAR REFERENCES orders(id) ON DELETE SET NULL, session_id VARCHAR(200),
        event_type VARCHAR(30) NOT NULL, revenue FLOAT NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_upsell_events_upsell_id ON upsell_events(upsell_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_upsell_events_event_type ON upsell_events(event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_upsell_events_created_at ON upsell_events(created_at DESC)")
    op.execute("""CREATE TABLE IF NOT EXISTS order_upsells (
        id VARCHAR PRIMARY KEY, order_id VARCHAR NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        upsell_id VARCHAR NOT NULL REFERENCES upsells(id) ON DELETE CASCADE,
        product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL,
        unit_price FLOAT NOT NULL, quantity INTEGER NOT NULL DEFAULT 1,
        revenue FLOAT NOT NULL DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_upsells_order_id ON order_upsells(order_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_upsells_upsell_id ON order_upsells(upsell_id)")

    for table in TABLES:
        op.add_column(table, sa.Column('tenant_id', sa.String(), nullable=True))
        op.execute(sa.text(
            f'ALTER TABLE {table} ADD CONSTRAINT {_fk(table)} '
            'FOREIGN KEY (tenant_id) REFERENCES tenants(id) NOT VALID'
        ))
        op.create_index(_idx(table), table, ['tenant_id', 'id'], unique=True)
    for table, columns, name in UNIQUES:
        op.create_unique_constraint(name, table, list(columns))

def downgrade():
    for table, _columns, name in reversed(UNIQUES):
        op.drop_constraint(name, table, type_='unique')
    for table in reversed(TABLES):
        op.drop_index(_idx(table), table_name=table)
        op.drop_constraint(_fk(table), table, type_='foreignkey')
        op.drop_column(table, 'tenant_id')
