'''Backfill legacy tenant ownership for operational RBAC and catalog.'''
from alembic import op
import sqlalchemy as sa

revision = '20260724_tenant_catalog_backfill'
down_revision = '20260723_tenant_catalog_expand'
branch_labels = None
depends_on = None

LEGACY_TENANT_ID = 'tenant-legacy-default'
TABLES = (
    'roles', 'role_permissions', 'user_permissions', 'admin_audit_logs',
    'products', 'product_categories', 'product_sizes', 'product_crust_types',
    'product_drink_variants', 'best_seller_config', 'multi_flavors_config',
    'product_promotions', 'product_promotion_combinations', 'promotions',
    'promotion_landing_pages', 'campaigns', 'campaign_products',
    'promotional_kits', 'promotional_kit_items', 'upsells', 'upsell_metrics',
    'upsell_events', 'order_upsells', 'home_catalog_config', 'theme_settings',
)
UNIQUE_PREFLIGHTS = (
    ('roles', 'name'),
    ('product_categories', 'name'),
    ('campaigns', 'slug'),
    ('promotion_landing_pages', 'slug'),
    ('upsell_metrics', 'upsell_id'),
)

def upgrade():
    bind = op.get_bind()
    exists = bind.execute(
        sa.text('SELECT 1 FROM tenants WHERE id = :tenant_id AND deleted_at IS NULL'),
        {'tenant_id': LEGACY_TENANT_ID},
    ).scalar()
    if exists != 1:
        raise RuntimeError('Legacy tenant is missing; refusing tenant backfill')
    for table, column in UNIQUE_PREFLIGHTS:
        duplicate = bind.execute(
            sa.text(
                f'SELECT {column} FROM {table} '
                f'WHERE {column} IS NOT NULL '
                'AND (tenant_id IS NULL OR tenant_id = :tenant_id) '
                f'GROUP BY {column} HAVING COUNT(*) > 1 LIMIT 1'
            ),
            {'tenant_id': LEGACY_TENANT_ID},
        ).scalar()
        if duplicate is not None:
            raise RuntimeError(
                f'Duplicate {table}.{column} blocks legacy tenant backfill'
            )
    for table in TABLES:
        bind.execute(
            sa.text(f'UPDATE {table} SET tenant_id = :tenant_id WHERE tenant_id IS NULL'),
            {'tenant_id': LEGACY_TENANT_ID},
        )

def downgrade():
    # Tenant attribution is business data and must not be erased on rollback.
    pass
