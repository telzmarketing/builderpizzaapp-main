"""Add tenant-scoped supplier contracts to Finance."""

from alembic import op
import sqlalchemy as sa


revision = "20261125_finance_contracts"
down_revision = "20261124_finance_projection_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_contracts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("counterparty_id", sa.String(), sa.ForeignKey("finance_counterparties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("contract_number", sa.String(length=100), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("renewal_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("billing_period", sa.String(length=30), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_admin_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft','active','expired','cancelled')", name="ck_finance_contracts_status"),
        sa.CheckConstraint("amount >= 0", name="ck_finance_contracts_amount"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_finance_contracts_period"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_finance_contracts_tenant_id_id"),
    )
    op.create_index("ix_finance_contracts_counterparty_id", "finance_contracts", ["counterparty_id"])
    op.create_index("ix_finance_contracts_status", "finance_contracts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_finance_contracts_status", table_name="finance_contracts")
    op.drop_index("ix_finance_contracts_counterparty_id", table_name="finance_contracts")
    op.drop_table("finance_contracts")
