"""add generic payment provider fields

Revision ID: 20260702_asaas_payment_generic_fields
Revises: 20260702_asaas_multi_gateway_config
Create Date: 2026-07-02
"""
from __future__ import annotations

from alembic import op

revision = "20260702_asaas_payment_generic_fields"
down_revision = "20260702_asaas_multi_gateway_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS provider_payment_id VARCHAR(160)")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS provider_customer_id VARCHAR(160)")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS provider_status VARCHAR(80)")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS currency VARCHAR(3) DEFAULT 'BRL'")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS installments INTEGER")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS pix_payload TEXT")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS pix_qr_code TEXT")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS pix_expires_at TIMESTAMPTZ")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS provider_error_code VARCHAR(120)")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS provider_error_message TEXT")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS refunded_at TIMESTAMPTZ")
    op.execute("UPDATE payments SET provider_payment_id = mercado_pago_payment_id WHERE provider_payment_id IS NULL AND mercado_pago_payment_id IS NOT NULL")
    op.execute("UPDATE payments SET currency = 'BRL' WHERE currency IS NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_payments_provider_payment_id ON payments(provider, provider_payment_id) WHERE provider_payment_id IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_provider_customer_id ON payments(provider, provider_customer_id) WHERE provider_customer_id IS NOT NULL")

    op.execute("ALTER TABLE payment_events ADD COLUMN IF NOT EXISTS provider_event_id VARCHAR(200)")
    op.execute("ALTER TABLE payment_events ADD COLUMN IF NOT EXISTS provider_payment_id VARCHAR(160)")
    op.execute("ALTER TABLE payment_events ADD COLUMN IF NOT EXISTS payload_hash VARCHAR(64)")
    op.execute("ALTER TABLE payment_events ADD COLUMN IF NOT EXISTS processing_status VARCHAR(30) DEFAULT 'received'")
    op.execute("ALTER TABLE payment_events ADD COLUMN IF NOT EXISTS error_message TEXT")
    op.execute("ALTER TABLE payment_events ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ")
    op.execute("UPDATE payment_events SET provider_payment_id = mercado_pago_payment_id WHERE provider_payment_id IS NULL AND mercado_pago_payment_id IS NOT NULL")
    op.execute("UPDATE payment_events SET processing_status = 'processed' WHERE processing_status IS NULL AND processed_at IS NOT NULL")
    op.execute("UPDATE payment_events SET processing_status = 'received' WHERE processing_status IS NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_payment_events_provider_event_id ON payment_events(provider, provider_event_id) WHERE provider_event_id IS NOT NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_payment_events_provider_payload_hash ON payment_events(provider, payload_hash) WHERE provider_event_id IS NULL AND payload_hash IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payment_events_provider_payment_id ON payment_events(provider, provider_payment_id) WHERE provider_payment_id IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_payment_events_provider_payment_id")
    op.execute("DROP INDEX IF EXISTS ix_payment_events_provider_payload_hash")
    op.execute("DROP INDEX IF EXISTS ix_payment_events_provider_event_id")
    op.execute("ALTER TABLE payment_events DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE payment_events DROP COLUMN IF EXISTS error_message")
    op.execute("ALTER TABLE payment_events DROP COLUMN IF EXISTS processing_status")
    op.execute("ALTER TABLE payment_events DROP COLUMN IF EXISTS payload_hash")
    op.execute("ALTER TABLE payment_events DROP COLUMN IF EXISTS provider_payment_id")
    op.execute("ALTER TABLE payment_events DROP COLUMN IF EXISTS provider_event_id")

    op.execute("DROP INDEX IF EXISTS ix_payments_provider_customer_id")
    op.execute("DROP INDEX IF EXISTS ix_payments_provider_payment_id")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS refunded_at")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS cancelled_at")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS provider_error_message")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS provider_error_code")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS pix_expires_at")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS pix_qr_code")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS pix_payload")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS installments")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS currency")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS provider_status")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS provider_customer_id")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS provider_payment_id")
