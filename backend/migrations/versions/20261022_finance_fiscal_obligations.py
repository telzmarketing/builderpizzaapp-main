"""Add tenant-owned obligations derived from fiscal documents.

The source document is authoritative.  No installment or due date is inferred
when the source does not provide it; the obligation may therefore contain a
single amount with no due date until an operator supplies the payment terms.
"""
from alembic import op
import sqlalchemy as sa


revision = "20261022_finance_fiscal_obligations"
down_revision = "20261022_inventory_receipt_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("finance_transactions", sa.Column("obligation_id", sa.String(), nullable=True))
    op.create_index("ix_finance_transactions_obligation_id", "finance_transactions", ["obligation_id"])

    op.create_table(
        "finance_obligations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", name="fk_finance_obligations_tenant"), nullable=False),
        sa.Column("fiscal_document_id", sa.String(), sa.ForeignKey("fiscal_documents.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("receipt_document_id", sa.String(), sa.ForeignKey("inventory_receipt_documents.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("total_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("product_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("freight_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("supplier_name", sa.String(180), nullable=True),
        sa.Column("supplier_document", sa.String(40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_admin_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_finance_obligations_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "fiscal_document_id", name="uq_finance_obligations_tenant_document"),
        sa.UniqueConstraint("tenant_id", "receipt_document_id", name="uq_finance_obligations_tenant_receipt"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_finance_obligations_tenant_idempotency"),
        sa.CheckConstraint("status IN ('pending','partial','paid','cancelled')", name="ck_finance_obligation_status"),
        sa.CheckConstraint("total_amount > 0 AND product_amount >= 0 AND freight_amount >= 0 AND discount_amount >= 0 AND tax_amount >= 0", name="ck_finance_obligation_amounts"),
    )
    op.create_index("ix_finance_obligations_fiscal_document_id", "finance_obligations", ["fiscal_document_id"])
    op.create_index("ix_finance_obligations_status", "finance_obligations", ["status"])
    op.create_table(
        "finance_obligation_installments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", name="fk_finance_obligation_installments_tenant"), nullable=False),
        sa.Column("obligation_id", sa.String(), sa.ForeignKey("finance_obligations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finance_transaction_id", sa.String(), sa.ForeignKey("finance_transactions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("installment_number", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("paid_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_finance_obligation_installments_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "obligation_id", "installment_number", name="uq_finance_obligation_installment_number"),
        sa.CheckConstraint("installment_number > 0 AND amount > 0 AND paid_amount >= 0 AND paid_amount <= amount", name="ck_finance_obligation_installment_amounts"),
        sa.CheckConstraint("status IN ('pending','partial','paid','cancelled')", name="ck_finance_obligation_installment_status"),
    )
    op.create_index("ix_finance_obligation_installments_obligation_id", "finance_obligation_installments", ["obligation_id"])
    op.create_index("ix_finance_obligation_installments_finance_transaction_id", "finance_obligation_installments", ["finance_transaction_id"])
    op.create_foreign_key("fk_finance_transactions_obligation", "finance_transactions", "finance_obligations", ["obligation_id"], ["id"], ondelete="SET NULL")


def downgrade():
    raise RuntimeError("Forward-only: financial source obligations are audit records.")
