from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.database import Base


class Upsell(Base):
    __tablename__ = "upsells"

    id = Column(String, primary_key=True)
    internal_name = Column(String(200), nullable=False)
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    image_url = Column(Text, nullable=True)
    main_text = Column(String(500), nullable=False)
    secondary_text = Column(String(500), nullable=True)
    promotional_price = Column(Float, nullable=True)
    # trigger_type: product_in_cart | category | min_value | min_quantity
    trigger_type = Column(String(50), nullable=False, default="min_value")
    trigger_product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    trigger_category = Column(String(100), nullable=True)
    trigger_min_value = Column(Float, default=0.0, nullable=True)
    trigger_min_quantity = Column(Integer, default=1, nullable=True)
    # "0123456" → all days; subset e.g. "0145" → Mon/Tue/Fri/Sat
    allowed_weekdays = Column(String(20), default="0123456", nullable=True)
    start_time = Column(String(5), nullable=True)   # "HH:MM"
    end_time = Column(String(5), nullable=True)     # "HH:MM"
    priority = Column(Integer, default=0, nullable=False, index=True)
    display_limit = Column(Integer, default=1, nullable=False)
    active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    product = relationship("Product", foreign_keys=[product_id])
    trigger_product = relationship("Product", foreign_keys=[trigger_product_id])
    metrics = relationship("UpsellMetric", back_populates="upsell", uselist=False, cascade="all, delete-orphan")
    events = relationship("UpsellEvent", back_populates="upsell", cascade="all, delete-orphan")


class UpsellMetric(Base):
    __tablename__ = "upsell_metrics"

    id = Column(String, primary_key=True)
    upsell_id = Column(String, ForeignKey("upsells.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    views = Column(Integer, default=0, nullable=False)
    accepts = Column(Integer, default=0, nullable=False)
    rejects = Column(Integer, default=0, nullable=False)
    revenue = Column(Float, default=0.0, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    upsell = relationship("Upsell", back_populates="metrics")


class UpsellEvent(Base):
    __tablename__ = "upsell_events"

    id = Column(String, primary_key=True)
    upsell_id = Column(String, ForeignKey("upsells.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = Column(String, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(String(200), nullable=True, index=True)
    # event_type: viewed | accepted | rejected
    event_type = Column(String(30), nullable=False, index=True)
    revenue = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    upsell = relationship("Upsell", back_populates="events")


class OrderUpsell(Base):
    __tablename__ = "order_upsells"

    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    upsell_id = Column(String, ForeignKey("upsells.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    unit_price = Column(Float, nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    revenue = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
