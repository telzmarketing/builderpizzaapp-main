from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CameraIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    identifier: str = Field(min_length=1, max_length=80)
    station_id: str = Field(min_length=1, max_length=20)
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
    id: str
    name: str
    identifier: str
    manufacturer: str | None
    model: str | None
    ip_address: str | None
    port: int | None
    protocol: str
    station_id: str
    resolution: str | None
    orientation: str | None
    installation_height_cm: int | None
    status: str
    last_connected_at: datetime | None
    has_credentials: bool


class SessionIn(BaseModel):
    production_unit_id: str = Field(min_length=1, max_length=120)
    stage: str = Field(min_length=1, max_length=40)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    expected_photo_count: int = Field(default=5, ge=1, le=100)


class PhotoIn(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=200)
    original_storage_key: str = Field(min_length=1, max_length=2000)
    processed_storage_key: str | None = Field(default=None, max_length=2000)
    captured_at: datetime | None = None
    content_type: str | None = Field(default=None, max_length=120)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    byte_size: int | None = Field(default=None, ge=0)
    is_final: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class FinishIn(BaseModel):
    status: str = Field(pattern="^(complete|partial)$")

