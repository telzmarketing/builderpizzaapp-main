from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Any
from datetime import datetime
from backend.models.payment import PaymentMethod, PaymentStatus


SENSITIVE_CARD_KEYS = {
    "cardnumber",
    "creditcardnumber",
    "securitycode",
    "cardsecuritycode",
    "cvv",
    "cvc",
    "ccv",
}


def _normalize_payload_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _contains_raw_card_data(value: Any, path: tuple[str, ...] = ()) -> bool:
    if isinstance(value, dict):
        parent = _normalize_payload_key(path[-1]) if path else ""
        for key, nested in value.items():
            normalized = _normalize_payload_key(str(key))
            if normalized in SENSITIVE_CARD_KEYS:
                return True
            if parent in {"creditcard", "card"} and normalized in {"number", "securitycode", "cvv", "cvc", "ccv"}:
                return True
            if _contains_raw_card_data(nested, (*path, str(key))):
                return True
    if isinstance(value, list):
        return any(_contains_raw_card_data(item, path) for item in value)
    return False


class PaymentCreate(BaseModel):
    order_id: str
    amount: Optional[float] = None
    payment_method: Optional[PaymentMethod] = None
    token: Optional[str] = None
    payment_method_id: Optional[str] = None
    payment_type_id: Optional[str] = None
    installments: Optional[int] = None
    issuer_id: Optional[str | int] = None
    payer: Optional[dict[str, Any]] = None
    form_data: Optional[dict[str, Any]] = Field(default=None, alias="formData")

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def reject_raw_card_data_in_payload(cls, value: Any) -> Any:
        if _contains_raw_card_data(value):
            raise ValueError("Dados brutos de cartao nao podem ser enviados para a API de pagamentos.")
        return value

    @field_validator("form_data")
    @classmethod
    def reject_raw_card_data(cls, value: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if value is not None and _contains_raw_card_data(value):
            raise ValueError("Dados brutos de cartao nao podem ser enviados para a API de pagamentos.")
        return value


class PayOnDeliverySwitch(BaseModel):
    delivery_payment_method: str = "card"
    cash_needs_change: Optional[bool] = None
    cash_change_for: Optional[float] = Field(default=None, ge=0)


class PaymentOperationRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=240)
    value: Optional[float] = Field(default=None, gt=0)


class PaymentOut(BaseModel):
    id: str
    order_id: str
    method: PaymentMethod
    status: PaymentStatus
    amount: float
    provider: Optional[str] = None
    provider_payment_id: Optional[str] = None
    provider_customer_id: Optional[str] = None
    provider_status: Optional[str] = None
    mercado_pago_payment_id: Optional[str] = None
    external_reference: Optional[str] = None
    transaction_id: Optional[str] = None
    currency: Optional[str] = "BRL"
    installments: Optional[int] = None
    qr_code: Optional[str] = None
    qr_code_text: Optional[str] = None
    pix_payload: Optional[str] = None
    pix_qr_code: Optional[str] = None
    pix_expires_at: Optional[datetime] = None
    payment_url: Optional[str] = None
    provider_error_code: Optional[str] = None
    provider_error_message: Optional[str] = None
    pay_on_delivery: bool = False
    delivery_payment_method: Optional[str] = None
    cash_needs_change: Optional[bool] = None
    cash_change_for: Optional[float] = None
    created_at: datetime
    paid_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WebhookPayload(BaseModel):
    """
    Flexible webhook payload that handles both our internal format
    and the real Mercado Pago notification format.

    MP sends:
      { "action": "payment.updated", "data": { "id": "12345678" } }

    We normalize it: transaction_id = data.id, status = action-derived or "pending"
    """
    # Internal / generic fields
    transaction_id: Optional[str] = None
    status: str = "pending"
    order_id: Optional[str] = None
    amount: Optional[float] = None
    gateway: Optional[str] = None

    # Mercado Pago native fields
    action: Optional[str] = None          # e.g. "payment.updated"
    data: Optional[dict] = None           # {"id": "12345678"}
    id: Optional[str] = None              # MP notification id
    type: Optional[str] = None            # "payment"

    def model_post_init(self, __context) -> None:
        # Normalize MP webhook: extract transaction_id from data.id
        if self.data and not self.transaction_id:
            self.transaction_id = str(self.data.get("id", ""))
        # Derive status from action when not provided explicitly
        if self.action and self.status == "pending":
            if "payment" in self.action:
                self.status = "approved"   # will be re-validated via API call in service
