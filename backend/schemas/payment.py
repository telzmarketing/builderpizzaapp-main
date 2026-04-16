from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from backend.models.payment import PaymentMethod, PaymentStatus


class PaymentCreate(BaseModel):
    order_id: str
    amount: float
    payment_method: PaymentMethod


class PaymentOut(BaseModel):
    id: str
    order_id: str
    method: PaymentMethod
    status: PaymentStatus
    amount: float
    transaction_id: Optional[str] = None
    qr_code: Optional[str] = None
    qr_code_text: Optional[str] = None
    payment_url: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None

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
