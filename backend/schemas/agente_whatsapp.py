from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


SessionStatus = Literal["open", "waiting_human", "human", "ai_paused", "closed"]
SessionOrigin = Literal["inbound", "campaign", "order_status", "manual"]
MessageDirection = Literal["inbound", "outbound"]
MessageSenderType = Literal["customer", "ai", "human", "system"]


class AgenteWhatsAppSessionCreate(BaseModel):
    phone: str = Field(..., min_length=8)
    customer_id: str | None = None
    provider: str = "official"
    provider_contact_id: str | None = None
    origin: SessionOrigin = "manual"
    ai_enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgenteWhatsAppSessionUpdate(BaseModel):
    status: SessionStatus | None = None
    current_intent: str | None = None
    assigned_admin_id: str | None = None
    ai_enabled: bool | None = None
    automation_blocked: bool | None = None
    metadata: dict[str, Any] | None = None


class AgenteWhatsAppSessionOut(BaseModel):
    id: str
    customer_id: str | None
    customer_name: str | None = None
    phone: str
    provider: str
    provider_contact_id: str | None
    status: str
    origin: str
    current_intent: str | None
    last_message_at: datetime | None
    assigned_admin_id: str | None
    ai_enabled: bool
    automation_blocked: bool
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AgenteWhatsAppMessageCreate(BaseModel):
    direction: MessageDirection
    sender_type: MessageSenderType
    message_type: str = "text"
    body: str | None = None
    media_url: str | None = None
    provider_message_id: str | None = None
    provider_status: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class AgenteWhatsAppMessageOut(BaseModel):
    id: str
    session_id: str
    customer_id: str | None
    direction: str
    sender_type: str
    message_type: str
    body: str | None
    media_url: str | None
    provider_message_id: str | None
    provider_status: str | None
    error: str | None
    raw_payload: dict[str, Any]
    created_at: datetime
    delivered_at: datetime | None
    read_at: datetime | None


class AgenteWhatsAppEventCreate(BaseModel):
    session_id: str | None = None
    customer_id: str | None = None
    order_id: str | None = None
    event_type: str
    source: str = "agente_whatsapp"
    payload: dict[str, Any] = Field(default_factory=dict)


class AgenteWhatsAppEventOut(BaseModel):
    id: str
    session_id: str | None
    customer_id: str | None
    order_id: str | None
    event_type: str
    source: str
    payload: dict[str, Any]
    processed_at: datetime | None
    created_at: datetime


class AgenteWhatsAppDashboardOut(BaseModel):
    sessions_open: int
    sessions_human: int
    sessions_ai_paused: int
    messages_today: int
    inbound_today: int
    outbound_today: int
    campaigns_total: int
    stories_total: int


class AgenteWhatsAppToolOut(BaseModel):
    name: str
    description: str
    category: str
    input_schema: dict[str, Any]
    mutates_data: bool = False
    requires_confirmation: bool = False
    enabled: bool = True


class AgenteWhatsAppToolCallIn(BaseModel):
    tool_name: str = Field(..., min_length=2)
    arguments: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None
    customer_id: str | None = None


class AgenteWhatsAppToolCallOut(BaseModel):
    log_id: str | None = None
    tool_name: str
    success: bool
    data: dict[str, Any] | list[dict[str, Any]] | None = None
    error: str | None = None
    latency_ms: int


class AgenteWhatsAppOutboxOut(BaseModel):
    id: str
    message_id: str
    session_id: str
    customer_id: str | None
    phone: str
    provider: str
    message_type: str | None = None
    message_body: str | None = None
    status: str
    attempts: int
    max_attempts: int
    idempotency_key: str
    provider_message_id: str | None
    error: str | None
    next_attempt_at: datetime | None
    locked_at: datetime | None
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgenteWhatsAppOutboxSummaryOut(BaseModel):
    pending: int
    processing: int
    sent: int
    failed: int
    dead: int
    queued_messages: int


class AgenteWhatsAppOutboxProcessIn(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)


class AgenteWhatsAppOutboxProcessOut(BaseModel):
    enqueued: int
    processed: int
    sent: int
    failed: int


class AgenteWhatsAppOutboxMetricsOut(AgenteWhatsAppOutboxSummaryOut):
    oldest_pending_age_seconds: int | None
    avg_send_latency_seconds: float | None
    last_sent_at: datetime | None
    last_error_at: datetime | None
    last_error: str | None


class AgenteWhatsAppProviderStateOut(BaseModel):
    id: str
    provider: str
    status: str
    consecutive_failures: int
    failure_threshold: int
    last_failure_at: datetime | None
    last_success_at: datetime | None
    paused_at: datetime | None
    paused_until: datetime | None
    paused_reason: str | None
    created_at: datetime
    updated_at: datetime


class AgenteWhatsAppProviderPauseIn(BaseModel):
    reason: str = Field(default="Pausa manual pelo painel.", min_length=3)
    minutes: int = Field(default=30, ge=1, le=1440)


class AgenteWhatsAppOutboxAlertOut(BaseModel):
    level: str
    code: str
    message: str


class AgenteWhatsAppInternalAlertOut(BaseModel):
    id: str
    alert_type: str
    level: str
    status: str
    title: str
    message: str
    dedupe_key: str
    payload: dict[str, Any]
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class AgenteWhatsAppOutboxAlertsOut(BaseModel):
    alerts: list[AgenteWhatsAppOutboxAlertOut]
    providers: list[AgenteWhatsAppProviderStateOut]
    metrics: AgenteWhatsAppOutboxMetricsOut
    internal_alerts: list[AgenteWhatsAppInternalAlertOut] = Field(default_factory=list)
