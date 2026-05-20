from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import relationship

from backend.database import Base


class RestaurantTable(Base):
    __tablename__ = "restaurant_tables"

    id = Column(String, primary_key=True)
    number = Column(String(30), nullable=False, unique=True, index=True)
    name = Column(String(120), nullable=True)
    capacity = Column(Integer, nullable=False, default=2)
    location = Column(String(120), nullable=True)
    status = Column(String(30), nullable=False, default="available", index=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    reservations = relationship("Reservation", back_populates="table")
    sessions = relationship("TableSession", back_populates="table")


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_name = Column(String(200), nullable=False)
    customer_phone = Column(String(40), nullable=False)
    customer_email = Column(String(200), nullable=True)
    table_id = Column(String, ForeignKey("restaurant_tables.id", ondelete="SET NULL"), nullable=True, index=True)
    reservation_date = Column(Date, nullable=False, index=True)
    reservation_time = Column(Time, nullable=False)
    guests_count = Column(Integer, nullable=False, default=2)
    status = Column(String(30), nullable=False, default="pending", index=True)
    notes = Column(Text, nullable=True)
    source = Column(String(40), nullable=False, default="salao")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    customer = relationship("Customer")
    table = relationship("RestaurantTable", back_populates="reservations")


class TableSession(Base):
    __tablename__ = "table_sessions"

    id = Column(String, primary_key=True)
    table_id = Column(String, ForeignKey("restaurant_tables.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    opened_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    closed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(30), nullable=False, default="open", index=True)
    subtotal = Column(Float, nullable=False, default=0.0)
    service_fee = Column(Float, nullable=False, default=0.0)
    discount = Column(Float, nullable=False, default=0.0)
    total = Column(Float, nullable=False, default=0.0)
    waiter_name = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    table = relationship("RestaurantTable", back_populates="sessions")
    customer = relationship("Customer")
    orders = relationship("Order", back_populates="table_session")
    items = relationship("TableSessionItem", back_populates="session", cascade="all, delete-orphan")


class TableSessionItem(Base):
    __tablename__ = "table_session_items"

    id = Column(String, primary_key=True)
    table_session_id = Column(String, ForeignKey("table_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_name = Column(String(200), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False, default=0.0)
    total_price = Column(Float, nullable=False, default=0.0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    session = relationship("TableSession", back_populates="items")
    product = relationship("Product")
