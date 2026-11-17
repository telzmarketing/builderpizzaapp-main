"""Persist delivery-app financial projections on orders."""

from alembic import op
import sqlalchemy as sa


revision = "20261117_order_app_finance_snapshot"
down_revision = "20261117_delivery_app_finance"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders", sa.Column("app_finance_gross_amount", sa.Numeric(20, 2), nullable=True))
    op.add_column("orders", sa.Column("app_finance_deductions", sa.Numeric(20, 2), nullable=True))
    op.add_column("orders", sa.Column("app_finance_net_amount", sa.Numeric(20, 2), nullable=True))
    op.add_column("orders", sa.Column("app_finance_rules", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("orders", "app_finance_rules")
    op.drop_column("orders", "app_finance_net_amount")
    op.drop_column("orders", "app_finance_deductions")
    op.drop_column("orders", "app_finance_gross_amount")
