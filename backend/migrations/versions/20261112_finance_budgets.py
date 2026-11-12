"""Add tenant-scoped finance budgets and budget lines."""

from alembic import op
import sqlalchemy as sa


revision = "20261112_finance_budgets"
down_revision = "20261112_finance_bank_reconciliation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_budgets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", name="fk_finance_budgets_tenant"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_admin_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("period_end >= period_start", name="ck_finance_budgets_period"),
        sa.CheckConstraint("status IN ('draft', 'active', 'closed')", name="ck_finance_budgets_status"),
    )
    op.create_index("uq_finance_budgets_tenant_id_id", "finance_budgets", ["tenant_id", "id"], unique=True)
    op.create_index("ix_finance_budgets_period_start", "finance_budgets", ["period_start"])
    op.create_index("ix_finance_budgets_period_end", "finance_budgets", ["period_end"])
    op.create_index("ix_finance_budgets_status", "finance_budgets", ["status"])

    op.create_table(
        "finance_budget_lines",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", name="fk_finance_budget_lines_tenant"), nullable=False),
        sa.Column("budget_id", sa.String(), sa.ForeignKey("finance_budgets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.String(), sa.ForeignKey("finance_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cost_center", sa.String(120), nullable=True),
        sa.Column("entry_type", sa.String(20), nullable=False, server_default="expense"),
        sa.Column("planned_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("entry_type IN ('income', 'expense')", name="ck_finance_budget_lines_entry_type"),
        sa.CheckConstraint("planned_amount >= 0", name="ck_finance_budget_lines_amount"),
    )
    op.create_index("uq_finance_budget_lines_tenant_id_id", "finance_budget_lines", ["tenant_id", "id"], unique=True)
    op.create_index("ix_finance_budget_lines_budget_id", "finance_budget_lines", ["budget_id"])
    op.create_index("ix_finance_budget_lines_category_id", "finance_budget_lines", ["category_id"])
    op.create_index("ix_finance_budget_lines_cost_center", "finance_budget_lines", ["cost_center"])


def downgrade() -> None:
    op.drop_table("finance_budget_lines")
    op.drop_table("finance_budgets")
