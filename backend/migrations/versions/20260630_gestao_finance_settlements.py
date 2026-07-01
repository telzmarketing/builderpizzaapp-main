"""gestao finance settlements

Revision ID: 20260630_gestao_finance_settlements
Revises: 20260627_gestao_inventory_order_sale_reversal
"""
from __future__ import annotations

from alembic import op

revision = "20260630_gestao_finance_settlements"
down_revision = "20260627_gestao_inventory_order_sale_reversal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column_name in ("interest_amount", "fine_amount", "discount_amount", "fee_amount", "net_amount"):
        op.execute(
            f"""
            ALTER TABLE finance_transactions
            ADD COLUMN IF NOT EXISTS {column_name} FLOAT NOT NULL DEFAULT 0
            """
        )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_settlements (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            transaction_id VARCHAR NOT NULL REFERENCES finance_transactions(id) ON DELETE CASCADE,
            account_id VARCHAR REFERENCES finance_accounts(id) ON DELETE SET NULL,
            settled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            principal_amount FLOAT NOT NULL DEFAULT 0,
            interest_amount FLOAT NOT NULL DEFAULT 0,
            fine_amount FLOAT NOT NULL DEFAULT 0,
            discount_amount FLOAT NOT NULL DEFAULT 0,
            fee_amount FLOAT NOT NULL DEFAULT 0,
            net_amount FLOAT NOT NULL DEFAULT 0,
            payment_method VARCHAR(40),
            payment_reference VARCHAR(120),
            created_by_admin_id VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL,
            origin_type VARCHAR(60) NOT NULL DEFAULT 'manual',
            origin_id VARCHAR,
            idempotency_key VARCHAR(160),
            notes TEXT,
            cancelled_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    for column_name in (
        "tenant_id",
        "transaction_id",
        "account_id",
        "settled_at",
        "payment_method",
        "payment_reference",
        "created_by_admin_id",
        "origin_type",
        "origin_id",
        "idempotency_key",
        "cancelled_at",
    ):
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_finance_settlements_{column_name} ON finance_settlements({column_name})")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_settlements_idempotency
        ON finance_settlements(tenant_id, idempotency_key)
        WHERE idempotency_key IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS finance_settlements")
    for column_name in ("net_amount", "fee_amount", "discount_amount", "fine_amount", "interest_amount"):
        op.execute(f"ALTER TABLE finance_transactions DROP COLUMN IF EXISTS {column_name}")
