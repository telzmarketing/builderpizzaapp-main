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
