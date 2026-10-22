"""Tenant-safe unit based KDS production state."""
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, Boolean, CheckConstraint, text, JSON, Numeric
from sqlalchemy.orm import relationship
from backend.database import Base

def utcnow(): return datetime.now(timezone.utc)

class ProductionUnit(Base):
    __tablename__ = "production_units"
    __table_args__ = (
        Index("uq_production_units_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_production_units_tenant_item_index", "tenant_id", "order_item_id", "unit_index", unique=True),
        Index("ix_production_units_queue", "tenant_id", "state", "created_at"),
        ForeignKeyConstraint(["tenant_id", "order_id"], ["orders.tenant_id", "orders.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "order_item_id"], ["order_items.tenant_id", "order_items.id"], ondelete="RESTRICT"),
        CheckConstraint("unit_index > 0", name="ck_production_unit_index"),
        CheckConstraint("state IN ('unassigned','queued','assembling','assembled','baking','checking','ready','blocked','cancelled')", name="ck_production_unit_state"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    order_id = Column(String, nullable=False)
    order_item_id = Column(String, nullable=False)
    unit_index = Column(Integer, nullable=False)
    state = Column(String(24), nullable=False, default="unassigned", server_default="unassigned")
    requires_oven = Column(Boolean, nullable=False, default=False, server_default="false")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    attempts = relationship("ProductionAttempt", back_populates="unit", cascade="all, delete-orphan", order_by="ProductionAttempt.attempt_number")

class ProductionAttempt(Base):
    __tablename__ = "production_attempts"
    __table_args__ = (
        Index("uq_production_attempts_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_production_attempts_tenant_unit_number", "tenant_id", "production_unit_id", "attempt_number", unique=True),
        ForeignKeyConstraint(["tenant_id", "production_unit_id"], ["production_units.tenant_id", "production_units.id"], ondelete="RESTRICT"),
        CheckConstraint("attempt_number > 0", name="ck_production_attempt_number"),
        CheckConstraint("state IN ('queued','assembling','assembled','baking','checking','ready','blocked','cancelled')", name="ck_production_attempt_state"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    production_unit_id = Column(String, nullable=False)
    attempt_number = Column(Integer, nullable=False)
    state = Column(String(24), nullable=False, default="queued", server_default="queued")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    operator_id = Column(String, ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=True)
    previous_attempt_id = Column(String, ForeignKey("production_attempts.id", ondelete="RESTRICT"), nullable=True)
    assigned_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    assembly_finished_at = Column(DateTime(timezone=True))
    oven_started_at = Column(DateTime(timezone=True))
    oven_finished_at = Column(DateTime(timezone=True))
    checked_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    blocked_reason = Column(Text)
    check_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    unit = relationship("ProductionUnit", back_populates="attempts")

class KdsOperatorState(Base):
    __tablename__ = "kds_operator_states"
    __table_args__ = (
        Index("uq_kds_operator_states_tenant_user_station", "tenant_id", "user_id", "station_id", unique=True),
        Index("ix_kds_operator_states_available", "tenant_id", "station_id", "requested_state"),
        CheckConstraint("requested_state IN ('available','paused','offline')", name="ck_kds_operator_requested_state"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    user_id = Column(String, ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False)
    station_id = Column(String(80), nullable=False)
    requested_state = Column(String(20), nullable=False, default="offline", server_default="offline")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    operational_session_id = Column(String(120))
    last_heartbeat_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

class KdsAssignment(Base):
    __tablename__ = "kds_assignments"
    __table_args__ = (
        Index("uq_kds_assignments_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_kds_assignments_active_attempt", "tenant_id", "attempt_id", unique=True, postgresql_where=text("active = true")),
        Index("ix_kds_assignments_operator_queue", "tenant_id", "operator_id", "active", "position"),
        ForeignKeyConstraint(["tenant_id", "attempt_id"], ["production_attempts.tenant_id", "production_attempts.id"], ondelete="RESTRICT"),
        CheckConstraint("position >= 0", name="ck_kds_assignment_position"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    attempt_id = Column(String, nullable=False)
    operator_id = Column(String, ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False)
    position = Column(Integer, nullable=False, default=0, server_default="0")
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    assigned_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    released_at = Column(DateTime(timezone=True))
    reason = Column(Text)

class ProductionAttemptConsumption(Base):
    """Immutable audit line linking one physical attempt to consumed stock."""
    __tablename__ = "production_attempt_consumptions"
    __table_args__ = (
        Index("uq_production_attempt_consumptions_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_production_attempt_consumptions_attempt_item", "tenant_id", "attempt_id", "inventory_item_id", unique=True),
        ForeignKeyConstraint(["tenant_id", "attempt_id"], ["production_attempts.tenant_id", "production_attempts.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "inventory_item_id"], ["inventory_items.tenant_id", "inventory_items.id"], ondelete="RESTRICT"),
        CheckConstraint("quantity > 0", name="ck_production_attempt_consumption_quantity"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    attempt_id = Column(String, nullable=False)
    inventory_item_id = Column(String, nullable=False)
    quantity = Column(Numeric(24, 6), nullable=False)
    unit_cost = Column(Numeric(24, 8), nullable=False, default=0)
    movement_ids = Column(JSON, nullable=False, default=list)
    operation_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
