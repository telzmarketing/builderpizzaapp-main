from sqlalchemy import Column, String, Float, Enum, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from backend.database import Base


class PaymentMethod(str, enum.Enum):
    pix = "pix"
    credit_card = "credit_card"
    debit_card = "debit_card"
    cash = "cash"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False, unique=True)

    method = Column(Enum(PaymentMethod), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.pending)
    amount = Column(Float, nullable=False)

    # Gateway data
    transaction_id = Column(String(300), nullable=True)
    gateway = Column(String(50), default="mock")

    # PIX fields
    qr_code = Column(Text, nullable=True)
    qr_code_text = Column(Text, nullable=True)    # copia e cola

    # Card fields
    payment_url = Column(String(500), nullable=True)
    client_secret = Column(String(300), nullable=True)

    # Webhook
    webhook_data = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    paid_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="payment")
