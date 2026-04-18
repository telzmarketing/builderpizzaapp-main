"""
Shipping V2 — comprehensive freight management models.

Tables:
  shipping_config           — global delivery settings (single row)
  freight_type_configs      — which freight types are active + per-type settings
  shipping_neighborhoods    — per-neighborhood rules
  shipping_cep_ranges       — CEP range rules
  shipping_distance_rules   — km-band rules
  shipping_order_value_tiers — order-value bracket rules
  shipping_promotions        — time-bound or threshold-based promotions
  shipping_extra_rules       — surcharges, blocks, time-based extras
"""
from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime, Text
from datetime import datetime, timezone
from backend.database import Base


def _now():
    return datetime.now(timezone.utc)


class ShippingConfig(Base):
    """Global delivery configuration — always exactly one row (id='default')."""
    __tablename__ = "shipping_config"

    id = Column(String, primary_key=True, default="default")
    delivery_enabled = Column(Boolean, default=True)
    pickup_enabled = Column(Boolean, default=False)
    pickup_message = Column(String(300), default="Retire em nossa loja")
    min_order_value = Column(Float, default=0.0)
    default_estimated_time = Column(Integer, default=45)   # minutes
    max_delivery_distance = Column(Float, default=20.0)    # km
    default_base_fee = Column(Float, default=5.0)
    unavailable_message = Column(String(300), default="Infelizmente não entregamos nessa região ainda.")
    store_lat = Column(Float, nullable=True)
    store_lng = Column(Float, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class FreightTypeConfig(Base):
    """
    Controls which freight types are active and their priorities.

    freight_type values:
      fixed | by_neighborhood | by_cep_range | by_distance |
      by_order_value | free | pickup | scheduled
    """
    __tablename__ = "freight_type_configs"

    id = Column(String, primary_key=True)
    freight_type = Column(String(50), nullable=False, unique=True)
    active = Column(Boolean, default=False)
    priority = Column(Integer, default=0)   # higher = evaluated first
    # for fixed type
    fixed_value = Column(Float, default=0.0)
    # for free type (0 = always free, >0 = free above threshold)
    free_above_value = Column(Float, default=0.0)
    # for scheduled delivery
    scheduled_surcharge = Column(Float, default=0.0)
    scheduled_surcharge_type = Column(String(20), default="fixed")   # "fixed" | "percentage"
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class ShippingNeighborhood(Base):
    """Per-neighborhood shipping rule."""
    __tablename__ = "shipping_neighborhoods"

    id = Column(String, primary_key=True)
    name = Column(String(150), nullable=False)
    city = Column(String(150), default="")
    shipping_value = Column(Float, default=0.0)
    is_free = Column(Boolean, default=False)
    min_order_value = Column(Float, default=0.0)
    estimated_time_min = Column(Integer, default=45)
    notes = Column(Text, default="")
    active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class ShippingCepRange(Base):
    """Shipping rule for a CEP (postal code) range."""
    __tablename__ = "shipping_cep_ranges"

    id = Column(String, primary_key=True)
    name = Column(String(150), default="")
    cep_start = Column(String(9), nullable=False)
    cep_end = Column(String(9), nullable=False)
    shipping_value = Column(Float, default=0.0)
    min_order_value = Column(Float, default=0.0)
    estimated_time_min = Column(Integer, default=45)
    active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class ShippingDistanceRule(Base):
    """Shipping rule for a km range (base_fee + fee_per_km)."""
    __tablename__ = "shipping_distance_rules"

    id = Column(String, primary_key=True)
    name = Column(String(150), default="")
    km_min = Column(Float, default=0.0)
    km_max = Column(Float, default=5.0)
    base_fee = Column(Float, default=0.0)
    fee_per_km = Column(Float, default=0.0)
    min_fee = Column(Float, default=0.0)
    max_fee = Column(Float, default=999.0)
    estimated_time_min = Column(Integer, default=45)
    active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class ShippingOrderValueTier(Base):
    """Shipping fee bracket based on order subtotal."""
    __tablename__ = "shipping_order_value_tiers"

    id = Column(String, primary_key=True)
    name = Column(String(150), default="")
    order_value_min = Column(Float, default=0.0)
    order_value_max = Column(Float, nullable=True)   # None = no upper limit
    shipping_value = Column(Float, default=0.0)
    is_free = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class ShippingPromotion(Base):
    """
    Promotional / free-shipping rule.

    promo_type values:
      free_above_value    — free when subtotal >= min_order_value
      promotional_period  — fixed shipping_value within valid_from/valid_until
      free_by_neighborhood — free for listed neighborhood IDs (JSON list in neighborhood_ids)
      free_campaign       — unconditional free shipping (campaign banner)
    """
    __tablename__ = "shipping_promotions"

    id = Column(String, primary_key=True)
    name = Column(String(150), nullable=False)
    promo_type = Column(String(50), nullable=False)
    min_order_value = Column(Float, default=0.0)
    shipping_value = Column(Float, default=0.0)   # 0 = free
    neighborhood_ids = Column(Text, default="[]")  # JSON list of ShippingNeighborhood IDs
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    active = Column(Boolean, default=True)
    priority = Column(Integer, default=100)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class ShippingExtraRule(Base):
    """
    Surcharges, blocks, and time-based additions applied AFTER the base rule.

    rule_type values:
      time_surcharge      — add value during time_start–time_end window
      demand_surcharge    — manual toggle extra charge
      area_surcharge      — extra charge for a specific neighborhood/city (condition field)
      scheduled_surcharge — extra for scheduled deliveries
      region_block        — blocks delivery to a region (condition = city/neighborhood name)
    """
    __tablename__ = "shipping_extra_rules"

    id = Column(String, primary_key=True)
    rule_type = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False)
    value = Column(Float, default=0.0)
    value_type = Column(String(20), default="fixed")   # "fixed" | "percentage"
    condition = Column(String(300), default="")        # neighborhood/city name for matching
    message = Column(String(300), default="")
    active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    time_start = Column(String(5), nullable=True)      # "HH:MM"
    time_end = Column(String(5), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)
