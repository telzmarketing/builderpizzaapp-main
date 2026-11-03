from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class CameraIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    identifier: str = Field(min_length=1, max_length=80)
    station_id: str = Field(min_length=1, max_length=80)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    ip_address: str | None = Field(default=None, max_length=120)
    port: int | None = Field(default=None, ge=1, le=65535)
    protocol: str = Field(default="rtsp", min_length=1, max_length=20)
    connection_url: str | None = Field(default=None, max_length=2000)
    username: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, max_length=500)
    resolution: str | None = Field(default=None, max_length=40)
    orientation: str | None = Field(default=None, max_length=40)
    installation_height_cm: int | None = Field(default=None, ge=1, le=10000)
    status: str = Field(default="inactive", pattern="^(active|inactive)$")


class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; name: str; identifier: str; manufacturer: str | None; model: str | None
    ip_address: str | None; port: int | None; protocol: str; station_id: str
    resolution: str | None; orientation: str | None; installation_height_cm: int | None
    status: str; last_connected_at: datetime | None; has_credentials: bool


class SessionIn(BaseModel):
    production_unit_id: str = Field(min_length=1, max_length=120)
    production_attempt_id: str | None = Field(default=None, min_length=1, max_length=120)
    stage: str = Field(min_length=1, max_length=40)
    station_id: str | None = Field(default=None, max_length=80)
    camera_id: str | None = Field(default=None, min_length=1, max_length=120)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    expected_photo_count: int | None = Field(default=None, ge=1, le=100)
    zone_id: str | None = Field(default=None, min_length=1, max_length=120)


class PhotoIn(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=200)
    original_storage_key: str = Field(min_length=1, max_length=2000)
    processed_storage_key: str | None = Field(default=None, max_length=2000)
    captured_at: datetime | None = None
    content_type: str | None = Field(default=None, max_length=120)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    byte_size: int | None = Field(default=None, ge=0)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    processing_status: str = Field(default="captured", pattern="^(captured|processed|failed)$")
    is_final: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class FinishIn(BaseModel):
    status: str = Field(pattern="^(complete|partial)$")


class SettingsIn(BaseModel):
    photos_per_session: int = Field(default=5, ge=1, le=100)
    max_width_px: int = Field(default=1280, ge=320, le=10000)
    image_format: str = Field(default="webp", pattern="^(webp|jpeg|png)$")
    image_quality: int = Field(default=80, ge=1, le=100)
    retention_days: int = Field(default=7, ge=1, le=3650)
    enabled: bool = True


class ZoneIn(BaseModel):
    identifier: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    station_id: str = Field(min_length=1, max_length=80)
    camera_id: str | None = Field(default=None, min_length=1, max_length=120)
    exclusive: bool = True
    status: str = Field(default="active", pattern="^(active|inactive)$")


class StationIn(BaseModel):
    identifier: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=120)
    status: str = Field(default="active", pattern="^(active|inactive)$")


class StationOut(BaseModel):
    id: str
    name: str
    station_type: str
    status: str
    protected: bool


class CaptureConfigIn(BaseModel):
    station_id: str = Field(min_length=1, max_length=80)
    milestone_1_name: str = Field(min_length=1, max_length=80)
    milestone_1_seconds: int = Field(ge=0, le=86400)
    milestone_2_name: str = Field(min_length=1, max_length=80)
    milestone_2_seconds: int = Field(ge=0, le=86400)
    milestone_3_name: str = Field(min_length=1, max_length=80)
    milestone_3_seconds: int = Field(ge=0, le=86400)
    enabled: bool = True


class CaptureEventIn(BaseModel):
    milestone: str = Field(pattern=r"^milestone_[123]$")
    idempotency_key: str = Field(min_length=1, max_length=200)
    mode: str = Field(default="automatic", pattern="^(automatic|manual)$")
    photo_id: str | None = Field(default=None, min_length=1, max_length=120)


class CaptureEventOut(BaseModel):
    id: str
    session_id: str
    order_id: str
    production_unit_id: str
    station_id: str
    milestone: str
    mode: str
    status: str
    idempotency_key: str
    photo_id: str | None = None
    captured_at: datetime | None = None
    reason: str | None = None


class OccupyZoneIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=1, max_length=200)


class IncidentIn(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=120)
    photo_id: str | None = Field(default=None, max_length=120)
    zone_id: str | None = Field(default=None, max_length=120)
    details: dict[str, Any] = Field(default_factory=dict)


class EvidenceHoldIn(BaseModel):
    hold_key: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, max_length=120)
    photo_id: str | None = Field(default=None, max_length=120)
