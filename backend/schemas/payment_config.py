from datetime import datetime
from typing import Optional

from pydantic import BaseModel


PaymentProvider = str


class PaymentGatewayConfigOut(BaseModel):
    """Admin response schema. Secret keys are masked before returning."""

    id: str
    gateway: str
    sandbox: bool
    accept_pix: bool
    accept_credit_card: bool
    accept_debit_card: bool
    accept_cash: bool

    # Multi-gateway routing
    pix_provider: PaymentProvider = "mercado_pago"
    credit_card_provider: PaymentProvider = "mercado_pago"

    # Mercado Pago
    mp_enabled: bool = True
    mp_environment: str = "sandbox"
    mp_public_key: Optional[str] = None
    mp_access_token_masked: Optional[str] = None
    mp_webhook_secret_masked: Optional[str] = None
    mp_pix_enabled: bool = True
    mp_credit_card_enabled: bool = True
    mp_max_installments: int = 6
    mp_last_health_check_at: Optional[datetime] = None
    mp_last_health_check_status: str = "not_tested"
    mp_last_health_check_message: Optional[str] = None

    # ASAAS
    asaas_enabled: bool = False
    asaas_environment: str = "sandbox"
    asaas_api_key_masked: Optional[str] = None
    asaas_webhook_token_masked: Optional[str] = None
    asaas_pix_enabled: bool = False
    asaas_credit_card_enabled: bool = False
    asaas_max_installments: int = 1
    asaas_tokenization_status: str = "not_validated"
    asaas_last_health_check_at: Optional[datetime] = None
    asaas_last_health_check_status: str = "not_tested"
    asaas_last_health_check_message: Optional[str] = None

    # Legacy/unused gateway fields kept for response compatibility.
    stripe_publishable_key: Optional[str] = None
    stripe_secret_key_masked: Optional[str] = None
    pagseguro_email: Optional[str] = None
    pagseguro_token_masked: Optional[str] = None

    # Legacy standalone PIX fields.
    pix_key: Optional[str] = None
    pix_key_type: Optional[str] = None
    pix_beneficiary_name: Optional[str] = None
    pix_beneficiary_city: Optional[str] = None

    updated_at: datetime

    model_config = {"from_attributes": True}


def _mask(value: str | None) -> str | None:
    """Return a masked secret preview."""
    if not value:
        return None
    visible = value[-4:] if len(value) >= 4 else value
    return f"{'*' * 8}{visible}"


class PaymentGatewayConfigUpdate(BaseModel):
    gateway: Optional[str] = None
    sandbox: Optional[bool] = None

    # Multi-gateway routing.
    pix_provider: Optional[PaymentProvider] = None
    credit_card_provider: Optional[PaymentProvider] = None

    # Accepted methods.
    accept_pix: Optional[bool] = None
    accept_credit_card: Optional[bool] = None
    accept_debit_card: Optional[bool] = None
    accept_cash: Optional[bool] = None

    # Mercado Pago.
    mp_enabled: Optional[bool] = None
    mp_environment: Optional[str] = None
    mp_public_key: Optional[str] = None
    mp_access_token: Optional[str] = None
    mp_webhook_secret: Optional[str] = None
    mp_pix_enabled: Optional[bool] = None
    mp_credit_card_enabled: Optional[bool] = None
    mp_max_installments: Optional[int] = None
    mp_last_health_check_status: Optional[str] = None
    mp_last_health_check_message: Optional[str] = None

    # ASAAS.
    asaas_enabled: Optional[bool] = None
    asaas_environment: Optional[str] = None
    asaas_api_key: Optional[str] = None
    asaas_webhook_token: Optional[str] = None
    asaas_pix_enabled: Optional[bool] = None
    asaas_credit_card_enabled: Optional[bool] = None
    asaas_max_installments: Optional[int] = None
    asaas_tokenization_status: Optional[str] = None
    asaas_last_health_check_status: Optional[str] = None
    asaas_last_health_check_message: Optional[str] = None

    # Legacy gateway fields.
    stripe_publishable_key: Optional[str] = None
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    pagseguro_email: Optional[str] = None
    pagseguro_token: Optional[str] = None

    # Legacy standalone PIX fields.
    pix_key: Optional[str] = None
    pix_key_type: Optional[str] = None
    pix_beneficiary_name: Optional[str] = None
    pix_beneficiary_city: Optional[str] = None


class PaymentGatewayRoutingUpdate(BaseModel):
    pix_provider: Optional[PaymentProvider] = None
    credit_card_provider: Optional[PaymentProvider] = None


class PaymentProviderConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    environment: Optional[str] = None
    api_key: Optional[str] = None
    webhook_token: Optional[str] = None
    public_key: Optional[str] = None
    access_token: Optional[str] = None
    webhook_secret: Optional[str] = None
    pix_enabled: Optional[bool] = None
    credit_card_enabled: Optional[bool] = None
    max_installments: Optional[int] = None
    tokenization_status: Optional[str] = None
