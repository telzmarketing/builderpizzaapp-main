from sqlalchemy import Column, String, Boolean, Float, Integer, Enum, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from backend.database import Base


class LogisticsSettings(Base):
    __tablename__ = "logistics_settings"

    id                         = Column(String, primary_key=True, default="default")
    auto_assign                = Column(Boolean, default=False)
    max_concurrent_deliveries  = Column(Integer, default=3)
    default_estimated_minutes  = Column(Integer, default=40)
    confirmation_code_enabled  = Column(Boolean, default=True)
    rate_per_delivery          = Column(Float, default=0.0, nullable=True)
    updated_at                 = Column(DateTime(timezone=True),
                                        default=lambda: datetime.now(timezone.utc),
                                        onupdate=lambda: datetime.now(timezone.utc))


class VehicleType(str, enum.Enum):
    motorcycle = "motorcycle"
    bicycle    = "bicycle"
    car        = "car"
    walking    = "walking"


class DeliveryPersonStatus(str, enum.Enum):
    available = "available"    # pronto para receber entrega
    busy      = "busy"         # em rota
    offline   = "offline"      # fora de serviço


class DeliveryStatus(str, enum.Enum):
    pending_assignment = "pending_assignment"
    assigned           = "assigned"
    picked_up          = "picked_up"
    on_the_way         = "on_the_way"
    delivered          = "delivered"
    completed          = "completed"
    failed             = "failed"
    cancelled          = "cancelled"


class DeliveryPerson(Base):
    __tablename__ = "delivery_persons"

    id            = Column(String, primary_key=True)
    name          = Column(String(200), nullable=False)
    phone         = Column(String(30), nullable=False)
    vehicle_type  = Column(Enum(VehicleType), default=VehicleType.motorcycle)
    status        = Column(Enum(DeliveryPersonStatus), default=DeliveryPersonStatus.offline)
    active        = Column(Boolean, default=True)

    # Driver app credentials
    email         = Column(String(200), nullable=True, unique=True)
    password_hash = Column(Text, nullable=True)

    # Documents & payment
    cpf           = Column(String(14), nullable=True)
    cnh           = Column(String(20), nullable=True)
    pix_key       = Column(String(200), nullable=True)

    # Real-time location (updated by mobile app)
    location_lat        = Column(Float, nullable=True)
    location_lng        = Column(Float, nullable=True)
    location_updated_at = Column(DateTime(timezone=True), nullable=True)

    # Stats
    total_deliveries = Column(Integer, default=0)
    average_rating   = Column(Float, default=5.0)

    created_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    deliveries = relationship("Delivery", back_populates="delivery_person")


class Delivery(Base):
    __tablename__ = "deliveries"

    id                 = Column(String, primary_key=True)
    order_id           = Column(String, ForeignKey("orders.id"), nullable=False, unique=True)
    delivery_person_id = Column(String, ForeignKey("delivery_persons.id"), nullable=True)

    status             = Column(Enum(DeliveryStatus), default=DeliveryStatus.pending_assignment)

    # Timing
    assigned_at        = Column(DateTime(timezone=True), nullable=True)
    picked_up_at       = Column(DateTime(timezone=True), nullable=True)
    delivered_at       = Column(DateTime(timezone=True), nullable=True)
    estimated_minutes  = Column(Integer, default=40)

    # Proof of delivery
    delivery_photo_url = Column(String(500), nullable=True)
    recipient_name     = Column(String(200), nullable=True)
    notes              = Column(Text, nullable=True)

    # Confirmation code (shown to customer, driver confirms via code)
    confirmation_code      = Column(String(4), nullable=True)
    confirmed_by_code_at   = Column(DateTime(timezone=True), nullable=True)

    # Rating
    rating         = Column(Integer, nullable=True)   # 1–5 given by customer
    rating_comment = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    delivery_person = relationship("DeliveryPerson", back_populates="deliveries")
    order           = relationship("Order", back_populates="delivery")
    events          = relationship("DeliveryEvent", back_populates="delivery",
                                   order_by="DeliveryEvent.created_at", cascade="all, delete-orphan")


class DeliveryEvent(Base):
    __tablename__ = "delivery_events"

    id            = Column(String, primary_key=True)
    delivery_id   = Column(String, ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False)
    event_type    = Column(String(80), nullable=False)
    description   = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    delivery = relationship("Delivery", back_populates="events")


class DeliveryEarning(Base):
    __tablename__ = "delivery_earnings"

    id                 = Column(String, primary_key=True)
    delivery_id        = Column(String, ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False)
    delivery_person_id = Column(String, ForeignKey("delivery_persons.id", ondelete="CASCADE"), nullable=False)
    amount             = Column(Float, default=0.0, nullable=False)
    status             = Column(String(20), default="pending", nullable=False)  # pending | paid
    period_date        = Column(Date, nullable=False)
    paid_at            = Column(DateTime(timezone=True), nullable=True)
    paid_by            = Column(String(200), nullable=True)
    notes              = Column(Text, nullable=True)
    created_at         = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    delivery        = relationship("Delivery")
    delivery_person = relationship("DeliveryPerson")


class GeocodeCache(Base):
    """Address → lat/lng cache to avoid repeated Nominatim calls."""
    __tablename__ = "geocode_cache"

    id         = Column(String(32), primary_key=True)  # sha256[:32] of normalised address
    query      = Column(Text, nullable=False)
    lat        = Column(Float, nullable=True)
    lng        = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
