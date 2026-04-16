from sqlalchemy import Column, String, Float, Boolean, Integer, Enum, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from backend.database import Base


class ShippingRuleType(str, enum.Enum):
    fixed = "fixed"                    # valor fixo independente do endereço
    per_distance = "per_distance"      # base + R$/km
    free_above = "free_above"          # grátis acima de X no subtotal
    promotional = "promotional"        # frete promocional com prioridade máxima


class ShippingZone(Base):
    __tablename__ = "shipping_zones"

    id = Column(String, primary_key=True)
    name = Column(String(100), nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    areas = relationship("ShippingZoneArea", back_populates="zone", cascade="all, delete-orphan")
    rules = relationship("ShippingRule", back_populates="zone")


class AreaType(str, enum.Enum):
    city = "city"
    neighborhood = "neighborhood"
    zip_prefix = "zip_prefix"


class ShippingZoneArea(Base):
    """Defines which addresses belong to a zone (by city, neighborhood, or zip prefix)."""
    __tablename__ = "shipping_zone_areas"

    id = Column(String, primary_key=True)
    zone_id = Column(String, ForeignKey("shipping_zones.id"), nullable=False)
    area_type = Column(Enum(AreaType), nullable=False)
    value = Column(String(100), nullable=False)      # e.g. "São Paulo", "Centro", "01310"

    zone = relationship("ShippingZone", back_populates="areas")


class ShippingRule(Base):
    __tablename__ = "shipping_rules"

    id = Column(String, primary_key=True)
    zone_id = Column(String, ForeignKey("shipping_zones.id"), nullable=True)
    name = Column(String(100), nullable=False)
    rule_type = Column(Enum(ShippingRuleType), nullable=False)

    priority = Column(Integer, default=0)           # higher = evaluated first
    active = Column(Boolean, default=True)

    # fixed / base cost
    base_price = Column(Float, default=0.0)

    # per_distance
    per_km_price = Column(Float, default=0.0)
    store_lat = Column(Float, nullable=True)
    store_lng = Column(Float, nullable=True)

    # free_above
    free_above_amount = Column(Float, nullable=True)

    # validity window (promotional)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    zone = relationship("ShippingZone", back_populates="rules")
