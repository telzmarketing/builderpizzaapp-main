from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from backend.models.delivery import VehicleType, DeliveryPersonStatus, DeliveryStatus


# ── Delivery Person ───────────────────────────────────────────────────────────

class DeliveryPersonCreate(BaseModel):
    name: str
    phone: str
    vehicle_type: VehicleType = VehicleType.motorcycle


class DeliveryPersonStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(available|offline)$")


class DeliveryPersonLocationUpdate(BaseModel):
    lat: float
    lng: float


class DeliveryPersonOut(BaseModel):
    id: str
    name: str
    phone: str
    vehicle_type: VehicleType
    status: DeliveryPersonStatus
    active: bool
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    location_updated_at: Optional[datetime] = None
    total_deliveries: int
    average_rating: float
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Delivery ──────────────────────────────────────────────────────────────────

class DeliveryAssignIn(BaseModel):
    order_id: str
    delivery_person_id: str
    estimated_minutes: int = 40


class DeliveryStatusUpdate(BaseModel):
    status: str


class DeliveryCompleteIn(BaseModel):
    recipient_name: Optional[str] = None
    delivery_photo_url: Optional[str] = None
    notes: Optional[str] = None


class DeliveryRateIn(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class DeliveryOut(BaseModel):
    id: str
    order_id: str
    delivery_person_id: Optional[str] = None
    status: DeliveryStatus
    assigned_at: Optional[datetime] = None
    picked_up_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    estimated_minutes: int
    delivery_photo_url: Optional[str] = None
    recipient_name: Optional[str] = None
    notes: Optional[str] = None
    rating: Optional[int] = None
    rating_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
