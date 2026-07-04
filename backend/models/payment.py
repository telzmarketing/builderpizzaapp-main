from sqlalchemy import Boolean, Column, String, Float, Enum, DateTime, ForeignKey, Text, Integer, UniqueConstraint
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
    provider_payment_id = Column(String(160), nullable=True)
    provider_customer_id = Column(String(160), nullable=True)
    provider_status = Column(String(80), nullable=True)
    mercado_pago_payment_id = Column(String(100), nullable=True, unique=True)
    external_reference = Column(String(120), nullable=True)
    currency = Column(String(3), default="BRL")
    installments = Column(Integer, nullable=True)
    card_brand = Column(String(40), nullable=True)
    card_brand_logo = Column(String(80), nullable=True)

    # PIX fields
    qr_code = Column(Text, nullable=True)
    qr_code_text = Column(Text, nullable=True)    # copia e cola
    pix_payload = Column(Text, nullable=True)
    pix_qr_code = Column(Text, nullable=True)
    pix_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Card fields
    payment_url = Column(String(500), nullable=True)
    client_secret = Column(String(300), nullable=True)
    provider_error_code = Column(String(120), nullable=True)
    provider_error_message = Column(Text, nullable=True)

    # Pay-on-delivery details
    pay_on_delivery = Column(Boolean, default=False)
    delivery_payment_method = Column(String(20), nullable=True)  # cash | card
    cash_needs_change = Column(Boolean, nullable=True)
    cash_change_for = Column(Float, nullable=True)

    # Webhook
    webhook_data = Column(Text, nullable=True)
    raw_response = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    paid_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="payment")


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id = Column(String, primary_key=True)
    provider = Column(String(50), nullable=False, default="mercado_pago")
    event_type = Column(String(100), nullable=True)
    provider_event_id = Column(String(200), nullable=True)
    provider_payment_id = Column(String(160), nullable=True)
    payload_hash = Column(String(64), nullable=True)
    processing_status = Column(String(30), default="received")
    error_message = Column(Text, nullable=True)
    mercado_pago_payment_id = Column(String(100), nullable=True)
    external_reference = Column(String(120), nullable=True)
    raw_payload = Column(Text, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class PaymentProviderCustomer(Base):
    __tablename__ = "payment_provider_customers"
    __table_args__ = (
        UniqueConstraint("customer_id", "provider", name="uq_payment_provider_customer"),
        UniqueConstraint("provider", "provider_customer_id", name="uq_payment_provider_customer_external_id"),
    )

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)
    provider_customer_id = Column(String(160), nullable=False)
    external_reference = Column(String(160), nullable=True)
    raw_response_sanitized = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    customer = relationship("Customer", back_populates="payment_provider_customers")
