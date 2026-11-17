"""Tenant-scoped financial rules for delivery applications."""
from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from backend.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class DeliveryAppFinanceConfig(Base):
    __tablename__ = "delivery_app_finance_configs"
    __table_args__ = (UniqueConstraint("tenant_id", "app_key", name="uq_delivery_app_finance_tenant_app"), CheckConstraint("app_key IN ('partner_99','ifood','keeta')", name="ck_delivery_app_finance_config_app_key"), Index("ix_delivery_app_finance_tenant_active", "tenant_id", "active"))
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    app_key = Column(String(40), nullable=False)
    app_name = Column(String(120), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

class DeliveryAppFinanceRule(Base):
    __tablename__ = "delivery_app_finance_rules"
    __table_args__ = (CheckConstraint("rule_type IN ('commission','fee','freight','store_discount','deduction')", name="ck_delivery_app_finance_rule_type"), CheckConstraint("calculation_type IN ('percentage','fixed')", name="ck_delivery_app_finance_calculation_type"), CheckConstraint("value >= 0", name="ck_delivery_app_finance_rule_value"), Index("ix_delivery_app_finance_rules_tenant_config", "tenant_id", "config_id", "active"),)
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    config_id = Column(String, ForeignKey("delivery_app_finance_configs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(120), nullable=False)
    rule_type = Column(String(30), nullable=False)
    calculation_type = Column(String(20), nullable=False)
    value = Column(Numeric(20, 2), nullable=False, default=0)
    sort_order = Column(Integer, nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
