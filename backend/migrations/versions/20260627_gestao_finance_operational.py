"""gestao finance operational fields

Revision ID: 20260627_gestao_finance_operational
Revises: 20260627_gestao_finance_base
"""
from __future__ import annotations

from alembic import op

revision = "20260627_gestao_finance_operational"
down_revision = "20260627_gestao_finance_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_counterparties (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            name VARCHAR(180) NOT NULL,
            counterparty_type VARCHAR(40) NOT NULL DEFAULT 'supplier',
            document VARCHAR(40),
            phone VARCHAR(40),
            email VARCHAR(180),
            notes TEXT,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_counterparties_tenant_id ON finance_counterparties(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_counterparties_counterparty_type ON finance_counterparties(counterparty_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_counterparties_document ON finance_counterparties(document)")

    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS counterparty_id VARCHAR REFERENCES finance_counterparties(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS counterparty_type VARCHAR(40)")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS counterparty_name VARCHAR(180)")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS counterparty_document VARCHAR(40)")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS paid_amount FLOAT NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS document_number VARCHAR(80)")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS document_date DATE")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS payment_method VARCHAR(40)")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS payment_reference VARCHAR(120)")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS installment_group_id VARCHAR")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS installment_number INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS installment_total INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS order_id VARCHAR REFERENCES orders(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS payment_id VARCHAR REFERENCES payments(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS inventory_purchase_id VARCHAR REFERENCES inventory_purchases(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS created_by_admin_id VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS updated_by_admin_id VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_counterparty_id ON finance_transactions(counterparty_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_counterparty_type ON finance_transactions(counterparty_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_counterparty_document ON finance_transactions(counterparty_document)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_document_number ON finance_transactions(document_number)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_document_date ON finance_transactions(document_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_payment_method ON finance_transactions(payment_method)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_payment_reference ON finance_transactions(payment_reference)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_installment_group_id ON finance_transactions(installment_group_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_order_id ON finance_transactions(order_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_payment_id ON finance_transactions(payment_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_inventory_purchase_id ON finance_transactions(inventory_purchase_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_created_by_admin_id ON finance_transactions(created_by_admin_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_updated_by_admin_id ON finance_transactions(updated_by_admin_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_operational_due ON finance_transactions(tenant_id, entry_type, status, due_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_origin_lookup ON finance_transactions(tenant_id, origin_type, origin_id)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_transactions_origin_installment
        ON finance_transactions(tenant_id, origin_type, origin_id, installment_number)
        WHERE origin_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_payment_method")
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_document_date")
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_document_number")
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_counterparty_document")
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_counterparty_type")
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_counterparty_id")
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_payment_reference")
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_installment_group_id")
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_order_id")
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_payment_id")
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_inventory_purchase_id")
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_created_by_admin_id")
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_updated_by_admin_id")
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_operational_due")
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_origin_lookup")
    op.execute("DROP INDEX IF EXISTS uq_finance_transactions_origin_installment")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS updated_by_admin_id")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS created_by_admin_id")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS inventory_purchase_id")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS payment_id")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS order_id")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS installment_total")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS installment_number")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS installment_group_id")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS payment_reference")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS payment_method")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS document_date")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS document_number")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS paid_amount")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS counterparty_document")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS counterparty_name")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS counterparty_type")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS counterparty_id")
    op.execute("DROP TABLE IF EXISTS finance_counterparties")
