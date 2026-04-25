from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import relationship

from backend.database import Base


class StoreOperationSettings(Base):
    __tablename__ = "store_operation_settings"

    id = Column(String, primary_key=True, default="default")
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    manual_mode = Column(String(30), nullable=False, default="manual_open")
    closed_message = Column(Text, nullable=False, default="Loja fechada no momento.")
    allow_scheduled_orders = Column(Boolean, default=False, nullable=False)
    timezone = Column(String(80), nullable=False, default="America/Sao_Paulo")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class StoreWeeklySchedule(Base):
    __tablename__ = "store_weekly_schedules"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    weekday = Column(Integer, nullable=False, index=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    intervals = relationship(
        "StoreOperationInterval",
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="StoreOperationInterval.open_time",
    )


class StoreOperationInterval(Base):
    __tablename__ = "store_operation_intervals"

    id = Column(String, primary_key=True)
    schedule_id = Column(String, ForeignKey("store_weekly_schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    open_time = Column(Time, nullable=False)
    close_time = Column(Time, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    schedule = relationship("StoreWeeklySchedule", back_populates="intervals")


class StoreOperationException(Base):
    __tablename__ = "store_operation_exceptions"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    date = Column(Date, nullable=False, index=True)
    exception_type = Column(String(30), nullable=False)
    open_time = Column(Time, nullable=True)
    close_time = Column(Time, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class StoreOperationLog(Base):
    __tablename__ = "store_operation_logs"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    admin_id = Column(String, nullable=True)
    admin_email = Column(String(200), nullable=True)
    action = Column(String(80), nullable=False)
    entity = Column(String(80), nullable=False)
    entity_id = Column(String, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
