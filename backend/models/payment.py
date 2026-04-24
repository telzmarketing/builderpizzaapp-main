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
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"
    expired = "expired"
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
    provider = Column(String(50), default="mock")
    mercado_pago_payment_id = Column(String(100), nullable=True, unique=True)
    external_reference = Column(String(120), nullable=True)

    # PIX fields
    qr_code = Column(Text, nullable=True)
    qr_code_text = Column(Text, nullable=True)    # copia e cola

    # Card fields
    payment_url = Column(String(500), nullable=True)
    client_secret = Column(String(300), nullable=True)

    # Webhook
    webhook_data = Column(Text, nullable=True)
    raw_response = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    paid_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="payment")


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id = Column(String, primary_key=True)
    provider = Column(String(50), nullable=False, default="mercado_pago")
    event_type = Column(String(100), nullable=True)
    mercado_pago_payment_id = Column(String(100), nullable=True)
    external_reference = Column(String(120), nullable=True)
    raw_payload = Column(Text, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
