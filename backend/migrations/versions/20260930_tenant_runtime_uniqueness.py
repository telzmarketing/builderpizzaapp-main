"""Replace legacy global uniqueness with tenant-scoped contracts.

Revision ID: 20260930_tenant_runtime_uniqueness
Revises: 20260927_order_board_mvp
"""
from alembic import op
import sqlalchemy as sa


revision = "20260930_tenant_runtime_uniqueness"
down_revision = "20260927_order_board_mvp"
branch_labels = None
depends_on = None


GLOBAL_CONSTRAINTS = (
    ("customers", "customers_email_key"),
    ("customers", "customers_google_id_key"),
    ("orders", "orders_order_code_key"),
    ("orders", "orders_external_reference_key"),
    ("coupons", "coupons_code_key"),
    ("campaigns", "campaigns_slug_key"),
    ("product_categories", "product_categories_name_key"),
    ("promotion_landing_pages", "uq_promotion_landing_pages_slug"),
    ("customer_auth", "uq_customer_auth_customer_provider"),
    ("customer_auth", "uq_customer_auth_provider_identifier"),
    ("customer_channels", "uq_customer_channel_identifier"),
    ("customer_preferences", "customer_preferences_customer_id_key"),
)

GLOBAL_INDEXES = (
    "ix_customers_google_id_unique",
    "ix_orders_external_reference",
    "ix_orders_order_code",
)


def upgrade() -> None:
    bind = op.get_bind()
    invalid_coupon = bind.execute(sa.text(
        "SELECT 1 FROM coupons c LEFT JOIN tenants t ON t.id=c.tenant_id "
        "WHERE c.tenant_id IS NULL OR c.tenant_id='default' OR t.id IS NULL "
        "OR t.deleted_at IS NOT NULL LIMIT 1"
    )).scalar()
    if invalid_coupon:
        raise RuntimeError("Contract gate failed for coupons: invalid tenant ownership")

    for table, constraint in GLOBAL_CONSTRAINTS:
        op.execute(sa.text(
            f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{constraint}"'
        ))
    for index in GLOBAL_INDEXES:
        op.execute(sa.text(f'DROP INDEX IF EXISTS "{index}"'))

    op.create_index("uq_coupons_tenant_code", "coupons", ["tenant_id", "code"], unique=True)
    op.alter_column(
        "coupons", "tenant_id", existing_type=sa.String(), nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    # Restoring global uniqueness is unsafe after two tenants legitimately use
    # the same identifier. Keep the downgrade data-preserving and require an
    # explicit collision audit before any legacy constraint is reintroduced.
    op.alter_column("coupons", "tenant_id", existing_type=sa.String(), nullable=True)
    op.drop_index("uq_coupons_tenant_code", table_name="coupons")
