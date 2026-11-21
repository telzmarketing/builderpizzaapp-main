"""Persist tenant-scoped gateway settlements for order amendment deltas."""

from alembic import op
import sqlalchemy as sa


revision = "20261121_payment_amendment_settlement"
down_revision = "20261121_post_production_priority"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_settlements",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amendment_id", sa.String(), sa.ForeignKey("order_amendments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payment_id", sa.String(), sa.ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("finance_transaction_id", sa.String(), sa.ForeignKey("finance_transactions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_operation_id", sa.String(180), nullable=True),
        sa.Column("provider_status", sa.String(80), nullable=True),
        sa.Column("checkout_url", sa.String(1000), nullable=True),
        sa.Column("qr_code_text", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("direction IN ('charge', 'refund')", name="ck_payment_settlements_direction"),
        sa.CheckConstraint("status IN ('processing', 'pending', 'succeeded', 'failed')", name="ck_payment_settlements_status"),
        sa.CheckConstraint("amount > 0", name="ck_payment_settlements_amount_positive"),
    )
    op.create_index("uq_payment_settlements_tenant_id_id", "payment_settlements", ["tenant_id", "id"], unique=True)
    op.create_index(
        "uq_payment_settlements_tenant_amendment_direction",
        "payment_settlements",
        ["tenant_id", "amendment_id", "direction"],
        unique=True,
    )
    op.create_index("uq_payment_settlements_tenant_idempotency", "payment_settlements", ["tenant_id", "idempotency_key"], unique=True)
    op.create_index("ix_payment_settlements_tenant_payment_direction", "payment_settlements", ["tenant_id", "payment_id", "direction"])


def downgrade() -> None:
    if not op.get_context().as_sql:
        has_history = op.get_bind().execute(
            sa.text("SELECT EXISTS (SELECT 1 FROM payment_settlements)")
        ).scalar()
        if has_history:
            raise RuntimeError("Refusing to downgrade payment_settlements because settlement history exists")

    op.drop_index("ix_payment_settlements_tenant_payment_direction", table_name="payment_settlements")
    op.drop_index("uq_payment_settlements_tenant_idempotency", table_name="payment_settlements")
    op.drop_index("uq_payment_settlements_tenant_amendment_direction", table_name="payment_settlements")
    op.drop_index("uq_payment_settlements_tenant_id_id", table_name="payment_settlements")
    op.drop_table("payment_settlements")
