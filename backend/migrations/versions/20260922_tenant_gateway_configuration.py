"""Create an inert payment gateway configuration for every tenant.

Revision ID: 20260922_tenant_gateway_configuration
Revises: 20260920_customer_session_security
"""
from alembic import op


revision = "20260922_tenant_gateway_configuration"
down_revision = "20260920_customer_session_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Credentials are tenant secrets: never clone the legacy/global row.
    op.execute(
        """
        INSERT INTO payment_gateway_config (
            id, tenant_id, gateway, pix_provider, credit_card_provider,
            mp_enabled, mp_environment, mp_pix_enabled,
            mp_credit_card_enabled, mp_max_installments,
            mp_last_health_check_status,
            asaas_enabled, asaas_environment, asaas_pix_enabled,
            asaas_credit_card_enabled, asaas_max_installments,
            asaas_tokenization_status, asaas_last_health_check_status,
            accept_pix, accept_credit_card, accept_debit_card, accept_cash,
            sandbox, updated_at
        )
        SELECT
            'pgc-' || md5(tenant.id), tenant.id, 'mercadopago',
            'mercado_pago', 'mercado_pago',
            FALSE, 'sandbox', FALSE, FALSE, 6, 'not_tested',
            FALSE, 'sandbox', FALSE, FALSE, 1,
            'not_validated', 'not_tested',
            FALSE, FALSE, FALSE, TRUE, TRUE, NOW()
        FROM tenants tenant
        WHERE tenant.deleted_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM payment_gateway_config config
              WHERE config.tenant_id = tenant.id
          )
        """
    )


def downgrade() -> None:
    # Rows may contain tenant credentials after upgrade; never erase them.
    pass
