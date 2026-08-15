"""Allowlisted HTTP contracts for Master Central operational modules."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


HealthStatus = Literal["healthy", "degraded", "critical", "unknown"]
ConnectionStatus = Literal["healthy", "degraded", "failed", "unknown"]
JobStatus = Literal["queued", "running", "retrying", "succeeded", "failed", "dead", "cancelled", "unknown"]
ErrorSeverity = Literal["info", "warning", "error", "critical"]
ErrorStatus = Literal["open", "acknowledged", "resolved"]


class TenantSummaryOut(BaseModel):
    id: str
    name: str


class HealthComponentOut(BaseModel):
    key: str
    label: str
    status: HealthStatus
    checked_at: datetime | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    message: str | None = None


class PlatformHealthOut(BaseModel):
    status: HealthStatus
    generated_at: datetime
    stale: bool
    components: list[HealthComponentOut]
    alerts: list[str] = Field(default_factory=list)


class IntegrationCategoryOut(BaseModel):
    key: str
    label: str
    total: int = Field(ge=0)
    healthy: int = Field(ge=0)
    degraded: int = Field(ge=0)
    failed: int = Field(ge=0)
    unknown: int = Field(ge=0)


class IntegrationsOverviewOut(BaseModel):
    total: int = Field(ge=0)
    configured: int = Field(ge=0)
    healthy: int = Field(ge=0)
    degraded: int = Field(ge=0)
    failed: int = Field(ge=0)
    unknown: int = Field(ge=0)
    by_category: list[IntegrationCategoryOut]
    generated_at: datetime


class IntegrationConnectionOut(BaseModel):
    id: str
    tenant: TenantSummaryOut
    category: str
    provider: str
    status: ConnectionStatus
    configured: bool
    last_sync_at: datetime | None = None
    updated_at: datetime | None = None
    error_present: bool


class IntegrationConnectionPageOut(BaseModel):
    items: list[IntegrationConnectionOut]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)


class WorkerHeartbeatOut(BaseModel):
    key: str
    instance_key: str
    status: HealthStatus
    last_heartbeat_at: datetime | None = None
    stale: bool


class JobsOverviewOut(BaseModel):
    total: int = Field(ge=0)
    queued: int = Field(ge=0)
    running: int = Field(ge=0)
    retrying: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    dead: int = Field(ge=0)
    oldest_pending_at: datetime | None = None
    workers: list[WorkerHeartbeatOut]
    generated_at: datetime


class QueueSummaryOut(BaseModel):
    key: str
    label: str
    total: int = Field(ge=0)
    queued: int = Field(ge=0)
    running: int = Field(ge=0)
    retrying: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    dead: int = Field(ge=0)
    oldest_pending_at: datetime | None = None


class QueueListOut(BaseModel):
    items: list[QueueSummaryOut]
    generated_at: datetime


class JobItemOut(BaseModel):
    id: str
    tenant: TenantSummaryOut
    queue: str
    job_type: str
    status: JobStatus
    source_status: str
    attempts: int = Field(ge=0)
    max_attempts: int = Field(ge=0)
    created_at: datetime | None = None
    scheduled_at: datetime | None = None
    next_attempt_at: datetime | None = None
    locked_at: datetime | None = None
    updated_at: datetime | None = None
    finished_at: datetime | None = None
    age_seconds: int = Field(ge=0)
    error_present: bool


class JobPageOut(BaseModel):
    items: list[JobItemOut]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)


class GatewayRuntimeOut(BaseModel):
    status: HealthStatus
    version: str | None = None
    checked_at: datetime | None = None
    stale: bool


class GatewayOverviewOut(BaseModel):
    runtime: GatewayRuntimeOut
    total_instances: int = Field(ge=0)
    connected: int = Field(ge=0)
    disconnected: int = Field(ge=0)
    degraded: int = Field(ge=0)
    unknown: int = Field(ge=0)
    last_activity_at: datetime | None = None


class GatewayInstanceOut(BaseModel):
    id: str
    tenant: TenantSummaryOut
    name: str
    provider: str
    status: str
    phone_masked: str | None = None
    last_seen_at: datetime | None = None
    connected_at: datetime | None = None
    disconnected_at: datetime | None = None
    updated_at: datetime | None = None


class GatewayInstancePageOut(BaseModel):
    items: list[GatewayInstanceOut]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)


class GatewayLogOut(BaseModel):
    id: str
    action: str
    status: str
    message: str | None = None
    created_at: datetime | None = None


class GatewayLogListOut(BaseModel):
    items: list[GatewayLogOut]
    total: int = Field(ge=0)


class ErrorSourceSummaryOut(BaseModel):
    source: str
    total_open: int = Field(ge=0)


class ErrorsOverviewOut(BaseModel):
    total_open: int = Field(ge=0)
    critical_open: int = Field(ge=0)
    acknowledged: int = Field(ge=0)
    resolved: int = Field(ge=0)
    last_seen_at: datetime | None = None
    by_source: list[ErrorSourceSummaryOut]
    generated_at: datetime


class ErrorEventOut(BaseModel):
    id: str
    tenant: TenantSummaryOut | None = None
    fingerprint: str
    source: str
    severity: ErrorSeverity
    status: ErrorStatus
    error_code: str | None = None
    exception_type: str | None = None
    message: str
    method: str | None = None
    path: str | None = None
    request_id: str | None = None
    occurrence_count: int = Field(ge=1)
    first_seen_at: datetime
    last_seen_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None


class ErrorEventDetailOut(ErrorEventOut):
    acknowledgement_note: str | None = None
    resolution_note: str | None = None


class ErrorEventPageOut(BaseModel):
    items: list[ErrorEventOut]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)


class ErrorDispositionIn(BaseModel):
    note: str = Field(min_length=2, max_length=1000)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("note deve ter ao menos 2 caracteres")
        return normalized


class ByteCountOut(BaseModel):
    bytes: int = Field(ge=0)
    files: int = Field(ge=0)


class DiskUsageOut(BaseModel):
    total_bytes: int = Field(ge=0)
    used_bytes: int = Field(ge=0)
    free_bytes: int = Field(ge=0)
    usage_percent: float = Field(ge=0, le=100)


class StorageOverviewOut(BaseModel):
    generated_at: datetime
    stale: bool
    status: HealthStatus
    disk: DiskUsageOut
    uploads: ByteCountOut
    optimized: ByteCountOut
    baileys: ByteCountOut
    legacy_unattributed: ByteCountOut


class TenantStorageOut(BaseModel):
    tenant: TenantSummaryOut
    bytes: int = Field(ge=0)
    files: int = Field(ge=0)
    limit_bytes: int | None = Field(default=None, ge=0)
    usage_percent: float | None = Field(default=None, ge=0)
    usage_state: Literal["normal", "warning", "critical", "unknown"]


class TenantStoragePageOut(BaseModel):
    items: list[TenantStorageOut]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)


class BackupComponentOut(BaseModel):
    key: Literal["database", "uploads", "environment", "baileys"]
    status: HealthStatus
    size_bytes: int | None = Field(default=None, ge=0)
    validated: bool


class RestoreDrillOut(BaseModel):
    status: HealthStatus
    last_tested_at: datetime | None = None


class BackupsOverviewOut(BaseModel):
    generated_at: datetime
    stale: bool
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    status: HealthStatus
    age_seconds: int | None = Field(default=None, ge=0)
    schedule: str | None = None
    components: list[BackupComponentOut]
    restore_drill: RestoreDrillOut


class BackupRunOut(BaseModel):
    run_id: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: HealthStatus
    components: list[BackupComponentOut]
    failure_phase: str | None = None
    failure_code: str | None = None


class BackupRunListOut(BaseModel):
    items: list[BackupRunOut]
