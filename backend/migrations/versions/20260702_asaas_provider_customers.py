"""add payment provider customer mapping

Revision ID: 20260702_asaas_provider_customers
Revises: 20260702_asaas_payment_generic_fields
Create Date: 2026-07-02
"""
from __future__ import annotations

from alembic import op

revision = "20260702_asaas_provider_customers"
down_revision = "20260702_asaas_payment_generic_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_provider_customers (
            id VARCHAR PRIMARY KEY,
            customer_id VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            provider VARCHAR(50) NOT NULL,
            provider_customer_id VARCHAR(160) NOT NULL,
            external_reference VARCHAR(160),
            raw_response_sanitized TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_payment_provider_customer UNIQUE (customer_id, provider),
            CONSTRAINT uq_payment_provider_customer_external_id UNIQUE (provider, provider_customer_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_payment_provider_customers_provider ON payment_provider_customers(provider)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payment_provider_customers_external_reference ON payment_provider_customers(provider, external_reference) WHERE external_reference IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_payment_provider_customers_external_reference")
    op.execute("DROP INDEX IF EXISTS ix_payment_provider_customers_provider")
    op.execute("DROP TABLE IF EXISTS payment_provider_customers")
