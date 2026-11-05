from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from backend.database import Base


class PizzaGlobalSize(Base):
    __tablename__ = "pizza_global_sizes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_pizza_global_sizes_tenant_name"),
        Index("ix_pizza_global_sizes_tenant_active_order", "tenant_id", "active", "sort_order"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0, server_default="0")
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    is_default = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PizzaGlobalDoughType(Base):
    __tablename__ = "pizza_global_dough_types"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_pizza_global_dough_types_tenant_name"),
        Index("ix_pizza_global_dough_types_tenant_active_order", "tenant_id", "active", "sort_order"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price_addition = Column(Float, nullable=False, default=0.0, server_default="0")
    sort_order = Column(Integer, nullable=False, default=0, server_default="0")
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PizzaGlobalCrust(Base):
    __tablename__ = "pizza_global_crusts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_pizza_global_crusts_tenant_name"),
        Index("ix_pizza_global_crusts_tenant_active_order", "tenant_id", "active", "sort_order"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price_addition = Column(Float, nullable=False, default=0.0, server_default="0")
    sort_order = Column(Integer, nullable=False, default=0, server_default="0")
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
