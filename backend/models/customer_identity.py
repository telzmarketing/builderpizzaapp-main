from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.database import Base


def _now_utc():
    return datetime.now(timezone.utc)


class CustomerAuth(Base):
    __tablename__ = "customer_auth"
    __table_args__ = (
        UniqueConstraint("customer_id", "auth_provider", name="uq_customer_auth_customer_provider"),
        UniqueConstraint("auth_provider", "identifier", name="uq_customer_auth_provider_identifier"),
    )

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    auth_provider = Column(String(40), nullable=False, default="password")
    identifier = Column(String(255), nullable=True)
    password_hash = Column(Text, nullable=True)
    provider_subject = Column(String(255), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    customer = relationship("Customer")


class CustomerChannel(Base):
    __tablename__ = "customer_channels"
    __table_args__ = (
        UniqueConstraint("channel", "normalized_identifier", name="uq_customer_channel_identifier"),
    )

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    channel = Column(String(40), nullable=False)
    identifier = Column(String(255), nullable=False)
    normalized_identifier = Column(String(255), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    marketing_consent = Column(Boolean, nullable=False, default=False)
    source = Column(String(100), nullable=True)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    customer = relationship("Customer")


class CustomerPreference(Base):
    __tablename__ = "customer_preferences"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, unique=True)
    preferred_channel = Column(String(40), nullable=True)
    preferred_contact_time = Column(String(40), nullable=True)
    language = Column(String(10), nullable=False, default="pt_BR")
    accepts_ai_service = Column(Boolean, nullable=False, default=True)
    accepts_order_status = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    customer = relationship("Customer")
