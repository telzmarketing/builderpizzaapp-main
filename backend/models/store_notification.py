from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import relationship

from backend.database import Base


class StoreNotificationSettings(Base):
    __tablename__ = "store_notification_settings"

    id = Column(String, primary_key=True, default="default")
    enabled = Column(Boolean, default=True, nullable=False)
    real_orders_enabled = Column(Boolean, default=True, nullable=False)
    real_percentage = Column(Integer, default=70, nullable=False)
    manual_percentage = Column(Integer, default=30, nullable=False)
    initial_delay_seconds = Column(Integer, default=5, nullable=False)
    min_delay_seconds = Column(Integer, default=45, nullable=False)
    max_delay_seconds = Column(Integer, default=120, nullable=False)
    default_display_seconds = Column(Integer, default=7, nullable=False)
    prevent_same_product_sequence = Column(Boolean, default=True, nullable=False)
    prevent_same_neighborhood_sequence = Column(Boolean, default=False, nullable=False)
    only_during_store_hours = Column(Boolean, default=False, nullable=False)
    allowed_pages = Column(Text, default='["home", "cardapio", "product", "cart"]', nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class StoreNotification(Base):
    __tablename__ = "store_notifications"

    id = Column(String, primary_key=True)
    type = Column(String(20), default="manual", nullable=False)
    status = Column(String(20), default="active", nullable=False)
    internal_name = Column(String(200), nullable=False)
    display_name = Column(String(120), nullable=False)
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    neighborhood = Column(String(120), nullable=True)
    template_text = Column(Text, nullable=False)
    priority = Column(String(20), default="medium", nullable=False)
    weight = Column(Integer, default=1, nullable=False)
    display_seconds = Column(Integer, default=7, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    source_customer_id = Column(
        String,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    product = relationship("Product")
    days = relationship(
        "StoreNotificationDay",
        back_populates="notification",
        cascade="all, delete-orphan",
        order_by="StoreNotificationDay.weekday",
    )
    impressions = relationship("StoreNotificationImpression", back_populates="notification")


class StoreNotificationDay(Base):
    __tablename__ = "store_notification_days"

    id = Column(String, primary_key=True)
    notification_id = Column(
        String,
        ForeignKey("store_notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weekday = Column(Integer, nullable=False, index=True)

    notification = relationship("StoreNotification", back_populates="days")


class StoreNotificationImpression(Base):
    __tablename__ = "store_notification_impressions"

    id = Column(String, primary_key=True)
    notification_id = Column(
        String,
        ForeignKey("store_notifications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_type = Column(String(20), nullable=False)
    order_id = Column(String, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    neighborhood = Column(String(120), nullable=True)
    page = Column(String(40), nullable=True, index=True)
    displayed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    notification = relationship("StoreNotification", back_populates="impressions")
    product = relationship("Product")


class StoreNotificationCaptured(Base):
    __tablename__ = "store_notification_captured"

    id = Column(String, primary_key=True)
    order_id = Column(
        String,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    customer_id = Column(
        String,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_id = Column(
        String,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_name = Column(String(200), nullable=True)
    product_image = Column(String(500), nullable=True)
    neighborhood = Column(String(120), nullable=True)
    buyer_name = Column(String(120), nullable=True)
    order_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
