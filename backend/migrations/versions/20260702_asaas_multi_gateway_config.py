"""add ASAAS multi-gateway configuration

Revision ID: 20260702_asaas_multi_gateway_config
Revises: 20260701_whatsapp_audio_phase5_agent_response
Create Date: 2026-07-02
"""
from __future__ import annotations

from alembic import op

revision = "20260702_asaas_multi_gateway_config"
down_revision = "20260701_whatsapp_audio_phase5_agent_response"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS pix_provider VARCHAR(50) NOT NULL DEFAULT 'mercado_pago'")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS credit_card_provider VARCHAR(50) NOT NULL DEFAULT 'mercado_pago'")

    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS mp_enabled BOOLEAN DEFAULT TRUE")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS mp_environment VARCHAR(20) NOT NULL DEFAULT 'sandbox'")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS mp_pix_enabled BOOLEAN DEFAULT TRUE")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS mp_credit_card_enabled BOOLEAN DEFAULT TRUE")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS mp_max_installments INTEGER DEFAULT 6")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS mp_last_health_check_at TIMESTAMPTZ")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS mp_last_health_check_status VARCHAR(30) NOT NULL DEFAULT 'not_tested'")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS mp_last_health_check_message TEXT")

    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS asaas_enabled BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS asaas_environment VARCHAR(20) NOT NULL DEFAULT 'sandbox'")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS asaas_api_key VARCHAR(500)")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS asaas_webhook_token VARCHAR(300)")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS asaas_pix_enabled BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS asaas_credit_card_enabled BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS asaas_max_installments INTEGER DEFAULT 1")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS asaas_tokenization_status VARCHAR(30) NOT NULL DEFAULT 'not_validated'")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS asaas_last_health_check_at TIMESTAMPTZ")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS asaas_last_health_check_status VARCHAR(30) NOT NULL DEFAULT 'not_tested'")
    op.execute("ALTER TABLE payment_gateway_config ADD COLUMN IF NOT EXISTS asaas_last_health_check_message TEXT")

    op.execute("UPDATE payment_gateway_config SET gateway = 'mercadopago' WHERE id = 'default' AND (gateway IS NULL OR gateway IN ('mock', 'mercado_pago'))")
    op.execute("UPDATE payment_gateway_config SET pix_provider = 'mercado_pago' WHERE pix_provider IS NULL OR pix_provider = ''")
    op.execute("UPDATE payment_gateway_config SET credit_card_provider = 'mercado_pago' WHERE credit_card_provider IS NULL OR credit_card_provider = ''")


def downgrade() -> None:
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS asaas_last_health_check_message")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS asaas_last_health_check_status")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS asaas_last_health_check_at")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS asaas_tokenization_status")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS asaas_max_installments")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS asaas_credit_card_enabled")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS asaas_pix_enabled")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS asaas_webhook_token")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS asaas_api_key")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS asaas_environment")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS asaas_enabled")

    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS mp_last_health_check_message")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS mp_last_health_check_status")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS mp_last_health_check_at")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS mp_max_installments")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS mp_credit_card_enabled")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS mp_pix_enabled")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS mp_environment")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS mp_enabled")

    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS credit_card_provider")
    op.execute("ALTER TABLE payment_gateway_config DROP COLUMN IF EXISTS pix_provider")

