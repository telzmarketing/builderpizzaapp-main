"""Fail-closed access to credentials owned by one tenant."""
from sqlalchemy.orm import Session
import uuid
from backend.config import get_settings
from backend.core.exceptions import DomainError
from backend.models.payment_config import PaymentGatewayConfig

class TenantCredentialsDisabled(DomainError):
    http_status = 404
    def __init__(self):
        super().__init__("Credenciais por tenant nao estao habilitadas.", code="TenantCredentialsDisabled")

class TenantCredentialConfigurationError(DomainError):
    http_status = 503
    def __init__(self, message: str):
        super().__init__(message, code="TenantCredentialConfigurationError")

class TenantCredentialService:
    def __init__(self, db: Session):
        self._db = db

    def payment_gateway(self, tenant_id: str) -> PaymentGatewayConfig:
        if not get_settings().TENANT_CREDENTIALS_ENABLED:
            raise TenantCredentialsDisabled()
        normalized = (tenant_id or "").strip()
        if not normalized:
            raise TenantCredentialConfigurationError("Contexto de tenant obrigatorio para credenciais.")
        rows = (self._db.query(PaymentGatewayConfig)
                .filter(PaymentGatewayConfig.tenant_id == normalized).limit(2).all())
        if len(rows) != 1:
            raise TenantCredentialConfigurationError("Configuracao de pagamento do tenant ausente ou ambigua.")
        return rows[0]

    def create_inert_payment_gateway(self, tenant_id: str) -> PaymentGatewayConfig:
        """Create the tenant singleton without inheriting any global secret."""
        normalized = (tenant_id or "").strip()
        if not normalized:
            raise TenantCredentialConfigurationError("Contexto de tenant obrigatorio para credenciais.")
        rows = (self._db.query(PaymentGatewayConfig)
                .filter(PaymentGatewayConfig.tenant_id == normalized).limit(2).all())
        if len(rows) > 1:
            raise TenantCredentialConfigurationError("Configuracao de pagamento do tenant ambigua.")
        if rows:
            return rows[0]
        config = PaymentGatewayConfig(
            id=f"pgc-{uuid.uuid4()}",
            tenant_id=normalized,
            gateway="mercadopago",
            pix_provider="mercado_pago",
            credit_card_provider="mercado_pago",
            mp_enabled=False,
            mp_pix_enabled=False,
            mp_credit_card_enabled=False,
            asaas_enabled=False,
            asaas_pix_enabled=False,
            asaas_credit_card_enabled=False,
            pagarme_enabled=False,
            pagarme_pix_enabled=False,
            pagarme_credit_card_enabled=False,
            accept_pix=False,
            accept_credit_card=False,
            accept_debit_card=False,
            accept_cash=True,
        )
        self._db.add(config)
        self._db.flush()
        return config
