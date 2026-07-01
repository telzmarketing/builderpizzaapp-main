"""gestao finance base

Revision ID: 20260627_gestao_finance_base
Revises: 20260625_gestao_cmv_snapshots
"""
from __future__ import annotations

from alembic import op

revision = "20260627_gestao_finance_base"
down_revision = "20260625_gestao_cmv_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_accounts (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            name VARCHAR(140) NOT NULL,
            account_type VARCHAR(40) NOT NULL DEFAULT 'bank',
            opening_balance FLOAT NOT NULL DEFAULT 0,
            notes TEXT,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_accounts_tenant_id ON finance_accounts(tenant_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_categories (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            name VARCHAR(140) NOT NULL,
            entry_type VARCHAR(20) NOT NULL DEFAULT 'expense',
            dre_group VARCHAR(80) NOT NULL DEFAULT 'operational',
            parent_id VARCHAR REFERENCES finance_categories(id) ON DELETE SET NULL,
            notes TEXT,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_categories_tenant_id ON finance_categories(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_categories_entry_type ON finance_categories(entry_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_categories_parent_id ON finance_categories(parent_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_transactions (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            account_id VARCHAR REFERENCES finance_accounts(id) ON DELETE SET NULL,
            category_id VARCHAR REFERENCES finance_categories(id) ON DELETE SET NULL,
            entry_type VARCHAR(20) NOT NULL DEFAULT 'expense',
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            description VARCHAR(220) NOT NULL,
            amount FLOAT NOT NULL DEFAULT 0,
            competence_date DATE NOT NULL DEFAULT CURRENT_DATE,
            due_date DATE,
            paid_at TIMESTAMPTZ,
            origin_type VARCHAR(60) NOT NULL DEFAULT 'manual',
            origin_id VARCHAR,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_tenant_id ON finance_transactions(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_account_id ON finance_transactions(account_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_category_id ON finance_transactions(category_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_entry_type ON finance_transactions(entry_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_status ON finance_transactions(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_competence_date ON finance_transactions(competence_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_due_date ON finance_transactions(due_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_origin_type ON finance_transactions(origin_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_origin_id ON finance_transactions(origin_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS finance_transactions")
    op.execute("DROP TABLE IF EXISTS finance_categories")
    op.execute("DROP TABLE IF EXISTS finance_accounts")
