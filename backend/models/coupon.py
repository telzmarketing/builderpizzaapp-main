from sqlalchemy import Column, String, Float, Boolean, Integer, Enum, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from backend.database import Base


class CouponType(str, enum.Enum):
    percentage = "percentage"   # desconto em %
    fixed = "fixed"             # desconto em R$ fixo


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(String, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(String(300))
    icon = Column(String(50), default="🎟️")
    coupon_type = Column(Enum(CouponType), nullable=False, default=CouponType.percentage)
    discount_value = Column(Float, nullable=False)       # % or R$
    min_order_value = Column(Float, default=0.0)         # pedido mínimo
    max_uses = Column(Integer, nullable=True)            # None = ilimitado
    max_uses_per_customer = Column(Integer, nullable=True)  # None = ilimitado por cliente
    used_count = Column(Integer, default=0)
    expiry_date = Column(DateTime(timezone=True), nullable=True)
    active = Column(Boolean, default=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    orders = relationship("Order", back_populates="coupon")
    usages = relationship("CouponUsage", back_populates="coupon", cascade="all, delete-orphan")


class CouponUsage(Base):
    __tablename__ = "coupon_usages"

    id = Column(String, primary_key=True)
    coupon_id = Column(String, ForeignKey("coupons.id"), nullable=False)
    customer_id = Column(String, nullable=True)
    phone = Column(String(30), nullable=True)
    order_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    coupon = relationship("Coupon", back_populates="usages")
