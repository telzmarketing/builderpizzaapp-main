"""Add auditable bank statement imports for finance reconciliation."""

from alembic import op
import sqlalchemy as sa


revision = "20261112_finance_bank_reconciliation"
down_revision = "20261112_inventory_purchase_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_bank_statements",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", name="fk_finance_bank_statements_tenant"), nullable=False),
        sa.Column("account_id", sa.String(), sa.ForeignKey("finance_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("external_reference", sa.String(180), nullable=True),
        sa.Column("file_hash", sa.String(128), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("opening_balance", sa.Numeric(20, 2), nullable=True),
        sa.Column("closing_balance", sa.Numeric(20, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="imported"),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_admin_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_finance_bank_statements_tenant_id_id"),
        sa.CheckConstraint("status IN ('imported','reconciled','closed')", name="ck_finance_bank_statements_status"),
        sa.CheckConstraint("period_start IS NULL OR period_end IS NULL OR period_start <= period_end", name="ck_finance_bank_statements_period"),
    )
    op.create_index("ix_finance_bank_statements_account_id", "finance_bank_statements", ["account_id"])
    op.create_index("ix_finance_bank_statements_status", "finance_bank_statements", ["status"])
    op.create_index(
        "uq_finance_bank_statements_import",
        "finance_bank_statements",
        ["tenant_id", "account_id", "file_hash"],
        unique=True,
        postgresql_where=sa.text("file_hash IS NOT NULL"),
    )

    op.create_table(
        "finance_bank_statement_lines",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", name="fk_finance_bank_statement_lines_tenant"), nullable=False),
        sa.Column("statement_id", sa.String(), sa.ForeignKey("finance_bank_statements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.String(), sa.ForeignKey("finance_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("external_id", sa.String(180), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(220), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("balance", sa.Numeric(20, 2), nullable=True),
        sa.Column("reconciliation_status", sa.String(20), nullable=False, server_default="unmatched"),
        sa.Column("matched_transaction_id", sa.String(), sa.ForeignKey("finance_transactions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("matched_by_admin_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_finance_bank_statement_lines_tenant_id_id"),
        sa.UniqueConstraint("statement_id", "external_id", name="uq_finance_bank_statement_lines_external"),
        sa.CheckConstraint("reconciliation_status IN ('unmatched','suggested','matched','ignored','divergent')", name="ck_finance_bank_statement_lines_status"),
    )
    for name, table, columns in (
        ("ix_finance_bank_statement_lines_statement_id", "finance_bank_statement_lines", ["statement_id"]),
        ("ix_finance_bank_statement_lines_account_id", "finance_bank_statement_lines", ["account_id"]),
        ("ix_finance_bank_statement_lines_transaction_date", "finance_bank_statement_lines", ["transaction_date"]),
        ("ix_finance_bank_statement_lines_status", "finance_bank_statement_lines", ["reconciliation_status"]),
        ("ix_finance_bank_statement_lines_matched_transaction_id", "finance_bank_statement_lines", ["matched_transaction_id"]),
    ):
        op.create_index(name, table, columns)

    op.create_table(
        "finance_bank_reconciliation_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", name="fk_finance_bank_reconciliation_events_tenant"), nullable=False),
        sa.Column("statement_line_id", sa.String(), sa.ForeignKey("finance_bank_statement_lines.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("transaction_id", sa.String(), sa.ForeignKey("finance_transactions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("admin_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_finance_bank_reconciliation_events_tenant_id_id"),
        sa.CheckConstraint("action IN ('matched','unmatched','ignored')", name="ck_finance_bank_reconciliation_events_action"),
    )
    for name, columns in (
        ("ix_finance_bank_reconciliation_events_statement_line_id", ["statement_line_id"]),
        ("ix_finance_bank_reconciliation_events_action", ["action"]),
        ("ix_finance_bank_reconciliation_events_transaction_id", ["transaction_id"]),
        ("ix_finance_bank_reconciliation_events_admin_id", ["admin_id"]),
    ):
        op.create_index(name, "finance_bank_reconciliation_events", columns)


def downgrade() -> None:
    raise RuntimeError("Forward-only: bank statement history is an audit record.")
