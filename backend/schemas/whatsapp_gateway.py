from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


GatewayProvider = Literal["baileys"]
GatewayInstanceStatus = Literal["created", "connecting", "connected", "disconnected", "qr_required", "error"]


class WhatsAppGatewayInstanceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=180)
    phone_number: str | None = Field(default=None, max_length=40)
    provider: GatewayProvider = "baileys"
    tenant_id: str = Field(default="default", max_length=80)
    company_id: str = Field(default="default", max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WhatsAppGatewayInstanceOut(BaseModel):
    id: str
    tenant_id: str
    company_id: str
    name: str
    phone_number: str | None
    provider: str
    status: str
    qr_code: str | None
    connected_at: datetime | None
    disconnected_at: datetime | None
    last_seen_at: datetime | None
    metadata: dict[str, Any]
    created_at: datetime | None
    updated_at: datetime | None


class WhatsAppGatewayLogOut(BaseModel):
    id: str
    tenant_id: str
    company_id: str
    instance_id: str | None
    action: str
    status: str
    message: str
    metadata: dict[str, Any]
    created_at: datetime | None


class WhatsAppGatewaySchedulerSettingsOut(BaseModel):
    id: str
    tenant_id: str
    company_id: str
    auto_health_check_enabled: bool
    morning_check_time: str
    evening_check_time: str
    auto_update_check_enabled: bool
    auto_update_staging_enabled: bool
    auto_update_production_enabled: bool
    notify_admin_enabled: bool


class WhatsAppGatewayProviderStatusOut(BaseModel):
    provider: str
    package_name: str
    installed: bool
    installed_version: str | None
    runtime_status: str
    production_auto_update_enabled: bool
    update_requires_confirmation: bool


class WhatsAppGatewayOverviewOut(BaseModel):
    total_instances: int
    connected_instances: int
    disconnected_instances: int
    qr_required_instances: int
    failed_instances: int
    provider: WhatsAppGatewayProviderStatusOut
    scheduler: WhatsAppGatewaySchedulerSettingsOut
    recent_logs: list[WhatsAppGatewayLogOut]


class WhatsAppGatewayUpdateStatusOut(BaseModel):
    package_name: str
    installed: bool
    installed_version: str | None
    available_version: str | None
    update_type: str | None
    risk_level: str | None
    check_id: str | None = None
    last_checked_at: datetime | None = None
    confirmation_required: bool
    confirmation_available: bool = False
    production_auto_update_enabled: bool
    message: str


class WhatsAppGatewayUpdateConfirmIn(BaseModel):
    check_id: str = Field(..., min_length=1)
    target_version: str = Field(..., min_length=1, max_length=80)
    confirm: bool = False


class WhatsAppGatewayUpdateConfirmOut(BaseModel):
    ok: bool
    check_id: str
    target_version: str
    status: str
    message: str


class WhatsAppGatewayRuntimeCommandOut(BaseModel):
    ok: bool
    message: str
    instance: WhatsAppGatewayInstanceOut
    runtime: dict[str, Any]
    qr_code: str | None = None
    qr_code_data_url: str | None = None


class WhatsAppGatewayRuntimeEventIn(BaseModel):
    event_type: str = Field(..., min_length=2, max_length=80)
    instance_id: str = Field(..., min_length=1, max_length=120)
    provider: str = "baileys"
    message: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)


class WhatsAppGatewayRuntimeEventOut(BaseModel):
    ok: bool
    received: int = 0
    duplicates: int = 0
    ignored: int = 0
    message: str
