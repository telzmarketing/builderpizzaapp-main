from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PaymentGatewayConfigOut(BaseModel):
    """
    Response schema — secret keys are masked before sending to the frontend.
    """
    id: str
    gateway: str
    sandbox: bool
    accept_pix: bool
    accept_credit_card: bool
    accept_debit_card: bool
    accept_cash: bool

    # Mercado Pago
    mp_public_key: Optional[str] = None
    mp_access_token_masked: Optional[str] = None      # last 4 chars only
    mp_webhook_secret_masked: Optional[str] = None    # last 4 chars only

    # Stripe
    stripe_publishable_key: Optional[str] = None
    stripe_secret_key_masked: Optional[str] = None

    # PagSeguro
    pagseguro_email: Optional[str] = None
    pagseguro_token_masked: Optional[str] = None

    # PIX
    pix_key: Optional[str] = None
    pix_key_type: Optional[str] = None
    pix_beneficiary_name: Optional[str] = None
    pix_beneficiary_city: Optional[str] = None

    updated_at: datetime

    model_config = {"from_attributes": True}


def _mask(value: str | None) -> str | None:
    """Returns '••••••••1234' style masked string."""
    if not value:
        return None
    visible = value[-4:] if len(value) >= 4 else value
    return f"{'•' * 8}{visible}"


class PaymentGatewayConfigUpdate(BaseModel):
    gateway: Optional[str] = None          # mock | mercadopago | stripe | pagseguro
    sandbox: Optional[bool] = None

    # Métodos aceitos
    accept_pix: Optional[bool] = None
    accept_credit_card: Optional[bool] = None
    accept_debit_card: Optional[bool] = None
    accept_cash: Optional[bool] = None

    # Mercado Pago
    mp_public_key: Optional[str] = None
    mp_access_token: Optional[str] = None
    mp_webhook_secret: Optional[str] = None

    # Stripe
    stripe_publishable_key: Optional[str] = None
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None

    # PagSeguro
    pagseguro_email: Optional[str] = None
    pagseguro_token: Optional[str] = None

    # PIX avulso
    pix_key: Optional[str] = None
    pix_key_type: Optional[str] = None
    pix_beneficiary_name: Optional[str] = None
    pix_beneficiary_city: Optional[str] = None
