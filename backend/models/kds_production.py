"""Tenant-safe unit based KDS production state."""
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, Boolean, CheckConstraint, text, JSON, Numeric
from sqlalchemy.dialects.postgresql import JSONB
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
        CheckConstraint("state IN ('unassigned','queued','checking_stock','aguardando_analise','atendimento','assembling','assembled','baking','checking','ready','blocked','cancelled')", name="ck_production_unit_state"),
        CheckConstraint("station_id IN ('pizza','pizza-1','pizza-2','esfiha','expedicao')", name="ck_production_unit_station"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    order_id = Column(String, nullable=False)
    order_item_id = Column(String, nullable=False)
    unit_index = Column(Integer, nullable=False)
    state = Column(String(24), nullable=False, default="unassigned", server_default="unassigned")
    # Operational routing only; the commercial order remains the single source of truth.
    station_id = Column(String(20), nullable=False, default="pizza", server_default="pizza")
    requires_oven = Column(Boolean, nullable=False, default=False, server_default="false")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    dispatch_completed_at = Column(DateTime(timezone=True), nullable=True)
    dispatch_completed_by = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
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
        CheckConstraint("state IN ('queued','checking_stock','aguardando_analise','atendimento','assembling','assembled','baking','checking','ready','blocked','cancelled')", name="ck_production_attempt_state"),
        Index("ix_production_attempts_stock_queue", "tenant_id", "state", "stock_requested_at"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    production_unit_id = Column(String, nullable=False)
    attempt_number = Column(Integer, nullable=False)
    priority = Column(Integer, nullable=False, default=0, server_default="0")
    state = Column(String(24), nullable=False, default="queued", server_default="queued")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    operator_id = Column(String, ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=True)
    previous_attempt_id = Column(String, ForeignKey("production_attempts.id", ondelete="RESTRICT"), nullable=True)
    assigned_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    stock_requested_at = Column(DateTime(timezone=True))
    stock_check_after = Column(DateTime(timezone=True))
    stock_consumption_mode = Column(String(30))
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


class ProductionEffect(Base):
    """Immutable tenant-scoped financial/stock effect audit record."""
    __tablename__ = "production_effects"
    __table_args__ = (
        Index("uq_production_effects_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_production_effects_tenant_kind_business_key", "tenant_id", "kind", "business_key", unique=True),
        Index("uq_production_effects_tenant_kind_idempotency_key", "tenant_id", "kind", "idempotency_key", unique=True),
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "attempt_id"],
            ["production_attempts.tenant_id", "production_attempts.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "source_effect_id"],
            ["production_effects.tenant_id", "production_effects.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("kind IN ('loss','reproduction','bonification')", name="ck_production_effect_kind"),
        CheckConstraint("length(request_hash) = 64", name="ck_production_effect_request_hash_length"),
        CheckConstraint("cost_total >= 0", name="ck_production_effect_cost_total_nonnegative"),
        CheckConstraint("discount_amount >= 0", name="ck_production_effect_discount_amount_nonnegative"),
        CheckConstraint(
            "length(trim(id)) > 0 AND length(trim(tenant_id)) > 0 "
            "AND length(trim(business_key)) > 0 AND length(trim(idempotency_key)) > 0 "
            "AND length(trim(order_id)) > 0 AND length(trim(actor_id)) > 0 "
            "AND length(trim(reason)) > 0",
            name="ck_production_effect_required_text_nonempty",
        ),
        CheckConstraint(
            "(attempt_id IS NULL OR length(trim(attempt_id)) > 0) "
            "AND (source_effect_id IS NULL OR length(trim(source_effect_id)) > 0)",
            name="ck_production_effect_optional_ids_nonempty",
        ),
        CheckConstraint(
            "(kind IN ('loss','reproduction') AND attempt_id IS NOT NULL) "
            "OR (kind = 'bonification' AND attempt_id IS NULL)",
            name="ck_production_effect_attempt_by_kind",
        ),
        CheckConstraint(
            "(kind = 'reproduction' AND source_effect_id IS NOT NULL) "
            "OR (kind IN ('loss','bonification') AND source_effect_id IS NULL)",
            name="ck_production_effect_source_by_kind",
        ),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    kind = Column(String(24), nullable=False)
    business_key = Column(String(200), nullable=False)
    idempotency_key = Column(String(200), nullable=False)
    request_hash = Column(String(64), nullable=False)
    order_id = Column(String, nullable=False)
    attempt_id = Column(String, nullable=True)
    source_effect_id = Column(String, nullable=True)
    actor_id = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    cost_total = Column(Numeric(24, 8), nullable=False, default=0, server_default="0")
    discount_amount = Column(Numeric(20, 2), nullable=False, default=0, server_default="0")
    snapshot_json = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
