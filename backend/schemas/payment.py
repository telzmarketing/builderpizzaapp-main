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


class AsaasCreditCardData(BaseModel):
    holder_name: str = Field(min_length=2, max_length=120, repr=False, alias="holderName")
    number: str = Field(min_length=12, max_length=19, repr=False)
    expiry_month: str = Field(min_length=1, max_length=2, repr=False, alias="expiryMonth")
    expiry_year: str = Field(min_length=2, max_length=4, repr=False, alias="expiryYear")
    ccv: str = Field(min_length=3, max_length=4, repr=False)

    model_config = {"populate_by_name": True}

    @field_validator("number", "expiry_month", "expiry_year", "ccv", mode="before")
    @classmethod
    def digits_only(cls, value: Any) -> str:
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    @field_validator("expiry_month")
    @classmethod
    def valid_month(cls, value: str) -> str:
        month = int(value or "0")
        if month < 1 or month > 12:
            raise ValueError("Mes de validade invalido.")
        return value.zfill(2)

    @field_validator("expiry_year")
    @classmethod
    def normalize_year(cls, value: str) -> str:
        if len(value) == 2:
            return f"20{value}"
        if len(value) != 4:
            raise ValueError("Ano de validade invalido.")
        return value


class AsaasCreditCardHolderInfo(BaseModel):
    name: str = Field(min_length=2, max_length=120, repr=False)
    email: str = Field(min_length=5, max_length=160, repr=False)
    cpf_cnpj: str = Field(min_length=11, max_length=14, repr=False, alias="cpfCnpj")
    postal_code: str = Field(min_length=8, max_length=8, repr=False, alias="postalCode")
    address_number: str = Field(min_length=1, max_length=20, repr=False, alias="addressNumber")
    address_complement: Optional[str] = Field(default=None, max_length=120, repr=False, alias="addressComplement")
    phone: Optional[str] = Field(default=None, max_length=20, repr=False)
    mobile_phone: Optional[str] = Field(default=None, max_length=20, repr=False, alias="mobilePhone")

    model_config = {"populate_by_name": True}

    @field_validator("cpf_cnpj", "postal_code", "phone", "mobile_phone", mode="before")
    @classmethod
    def normalize_digits(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        return "".join(ch for ch in str(value) if ch.isdigit())


class AsaasCreditCardPaymentCreate(BaseModel):
    order_id: str
    amount: Optional[float] = Field(default=None, gt=0)
    installments: int = Field(default=1, ge=1, le=21)
    credit_card: AsaasCreditCardData = Field(alias="creditCard", repr=False)
    credit_card_holder_info: AsaasCreditCardHolderInfo = Field(alias="creditCardHolderInfo", repr=False)

    model_config = {"populate_by_name": True}


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
    card_brand: Optional[str] = None
    card_brand_logo: Optional[str] = None
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
