"""Add tenant-scoped delivery app financial rules."""
from alembic import op
import sqlalchemy as sa

revision = "20261117_delivery_app_finance"
down_revision = "20261117_manual_order_discounts"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("delivery_app_finance_configs",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("app_key", sa.String(40), nullable=False), sa.Column("app_name", sa.String(120), nullable=False), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "app_key", name="uq_delivery_app_finance_tenant_app"), sa.CheckConstraint("app_key IN ('partner_99','ifood','keeta')", name="ck_delivery_app_finance_config_app_key"))
    op.create_index("ix_delivery_app_finance_tenant_active", "delivery_app_finance_configs", ["tenant_id", "active"])
    op.create_table("delivery_app_finance_rules",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("config_id", sa.String(), sa.ForeignKey("delivery_app_finance_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("rule_type", sa.String(30), nullable=False), sa.Column("calculation_type", sa.String(20), nullable=False), sa.Column("value", sa.Numeric(20, 2), nullable=False, server_default="0"), sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("rule_type IN ('commission','fee','freight','store_discount','deduction')", name="ck_delivery_app_finance_rule_type"), sa.CheckConstraint("calculation_type IN ('percentage','fixed')", name="ck_delivery_app_finance_calculation_type"), sa.CheckConstraint("value >= 0", name="ck_delivery_app_finance_rule_value"))
    op.create_index("ix_delivery_app_finance_rules_tenant_config", "delivery_app_finance_rules", ["tenant_id", "config_id", "active"])

def downgrade():
    op.drop_index("ix_delivery_app_finance_rules_tenant_config", table_name="delivery_app_finance_rules")
    op.drop_table("delivery_app_finance_rules")
    op.drop_index("ix_delivery_app_finance_tenant_active", table_name="delivery_app_finance_configs")
    op.drop_table("delivery_app_finance_configs")
