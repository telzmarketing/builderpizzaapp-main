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
    email: Optional[str] = None
    cpf: Optional[str] = None
    cnh: Optional[str] = None
    pix_key: Optional[str] = None
    password: Optional[str] = None


class DeliveryPersonUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    vehicle_type: Optional[VehicleType] = None
    email: Optional[str] = None
    cpf: Optional[str] = None
    cnh: Optional[str] = None
    pix_key: Optional[str] = None
    password: Optional[str] = None


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
    email: Optional[str] = None
    cpf: Optional[str] = None
    cnh: Optional[str] = None
    pix_key: Optional[str] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    location_updated_at: Optional[datetime] = None
    total_deliveries: int
    average_rating: float
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Driver App Auth ───────────────────────────────────────────────────────────

class DriverLoginIn(BaseModel):
    email: str
    password: str


class DriverLoginOut(BaseModel):
    token: str
    person: DeliveryPersonOut


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


class DeliveryConfirmIn(BaseModel):
    code: str = Field(..., min_length=4, max_length=4)


class DeliveryOut(BaseModel):
    id: str
    order_id: str
    delivery_person_id: Optional[str] = None
    status: DeliveryStatus
    assigned_at: Optional[datetime] = None
    picked_up_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    estimated_minutes: int
    confirmation_code: Optional[str] = None
    confirmed_by_code_at: Optional[datetime] = None
    delivery_photo_url: Optional[str] = None
    recipient_name: Optional[str] = None
    notes: Optional[str] = None
    rating: Optional[int] = None
    rating_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Logistics Settings ────────────────────────────────────────────────────────

class LogisticsSettingsOut(BaseModel):
    id: str
    auto_assign: bool
    max_concurrent_deliveries: int
    default_estimated_minutes: int
    confirmation_code_enabled: bool
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LogisticsSettingsUpdate(BaseModel):
    auto_assign: Optional[bool] = None
    max_concurrent_deliveries: Optional[int] = None
    default_estimated_minutes: Optional[int] = None
    confirmation_code_enabled: Optional[bool] = None
