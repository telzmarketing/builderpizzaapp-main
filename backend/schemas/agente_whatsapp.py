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


class AgenteWhatsAppConversationOut(AgenteWhatsAppSessionOut):
    last_message: AgenteWhatsAppMessageOut | None = None
    unread_count: int = 0
    attendance_mode: Literal["ai", "human"] = "ai"


class AgenteWhatsAppOperationalMetricsOut(BaseModel):
    chatbots_online: int = 0
    conversations_online: int = 0
    active_attendances: int = 0
    waiting_response: int = 0
    finalized_today: int = 0
    unread_messages: int = 0
    avg_response_time_seconds: float = 0
    avg_attendance_time_seconds: float = 0
    simultaneous_attendances: int = 0
    active_ai_agents: int = 0
    human_attendants_online: int = 0
    generated_at: datetime | None = None


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


class AgenteWhatsAppAIRespondIn(BaseModel):
    message: str = Field(..., min_length=1)
    auto_queue: bool = False
    record_inbound: bool = False


class AgenteWhatsAppAISettingsUpdate(BaseModel):
    enabled: bool | None = None
    provider: Literal["internal", "openai", "claude"] | None = None
    model: str | None = Field(default=None, min_length=2, max_length=120)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)
    prompt_base: str | None = None
    business_rules: str | None = None
    tone_of_voice: str | None = None
    objective: str | None = None
    transfer_instructions: str | None = None
    forbidden_topics: str | None = None
    allowed_tools: dict[str, Any] | None = None


class AgenteWhatsAppAIKeysUpdate(BaseModel):
    openai_api_key: str | None = Field(default=None, min_length=1, max_length=500)
    anthropic_api_key: str | None = Field(default=None, min_length=1, max_length=500)


class AgenteWhatsAppAISettingsOut(BaseModel):
    id: str
    enabled: bool
    provider: str
    model: str
    temperature: float
    max_tokens: int
    prompt_base: str
    business_rules: str
    tone_of_voice: str
    objective: str
    transfer_instructions: str
    forbidden_topics: str
    allowed_tools: dict[str, Any]
    openai_key_preview: str | None = None
    anthropic_key_preview: str | None = None
    updated_at: datetime | None = None


class AgenteWhatsAppAIProviderStatusOut(BaseModel):
    provider: str
    model: str
    internal: bool
    openai: bool
    claude: bool
    active: bool
    openai_key_preview: str | None = None
    anthropic_key_preview: str | None = None


class AgenteWhatsAppChannelSettingsUpdate(BaseModel):
    active_provider: Literal["official", "baileys"] | None = None
    whatsapp_gateway_instance_id: str | None = None


class AgenteWhatsAppChannelSettingsOut(BaseModel):
    id: str
    active_provider: str
    whatsapp_gateway_instance_id: str | None = None
    updated_at: datetime | None = None


class AgenteWhatsAppAITestIn(BaseModel):
    message: str | None = None


class AgenteWhatsAppAITestOut(BaseModel):
    provider: str
    model: str
    configured: bool
    response: str
    latency_ms: int
    tokens_input: int
    tokens_output: int
    prompt_preview: str


class AgenteWhatsAppAIToolTraceOut(BaseModel):
    tool_name: str
    success: bool
    error: str | None = None
    latency_ms: int
    arguments: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] | list[dict[str, Any]] | None = None


class AgenteWhatsAppAIGuardrailsOut(BaseModel):
    allowed_auto_queue: bool
    safe_for_suggestion: bool
    status: str
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recent_ai_responses: int
    recent_window_seconds: int
    consecutive_ai_outbound: int
    last_inbound_at: datetime | None = None
    last_ai_outbound_at: datetime | None = None
    session_status: str
    ai_enabled: bool
    automation_blocked: bool


class AgenteWhatsAppAIRespondOut(BaseModel):
    session_id: str
    intent: str
    response: str
    needs_human: bool
    auto_queued: bool
    message: AgenteWhatsAppMessageOut | None = None
    tool_calls: list[AgenteWhatsAppAIToolTraceOut] = Field(default_factory=list)
    enqueued: int = 0
    guardrails: AgenteWhatsAppAIGuardrailsOut
    manager_review: dict[str, Any] = Field(default_factory=dict)
    ai_settings: dict[str, Any] = Field(default_factory=dict)


class AgenteWhatsAppCampaignCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=300)
    message_template: str = Field(..., min_length=3)
    audience_type: str = Field(default="manual")
    phones: list[str] = Field(default_factory=list)
    campaign_type: str = "manual"
    scheduled_at: datetime | None = None


class AgenteWhatsAppCampaignOut(BaseModel):
    id: str
    name: str
    status: str
    campaign_type: str
    audience: dict[str, Any]
    message_template: str
    scheduled_at: datetime | None
    sent_count: int
    delivered_count: int
    read_count: int
    replied_count: int
    conversion_count: int
    revenue: float
    metrics: dict[str, Any]
    created_by: str | None
    created_at: datetime | None
    updated_at: datetime | None


class AgenteWhatsAppCampaignDispatchOut(BaseModel):
    campaign_id: str
    status: str
    recipients: int
    queued: int
    skipped: int
    enqueued: int


class AgenteWhatsAppCampaignTemplateOut(BaseModel):
    id: str
    name: str
    body: str
    category: str


class AgenteWhatsAppStoryCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=300)
    media_type: str = Field(..., pattern="^(image|video)$")
    media_url: str = Field(..., min_length=2)
    caption: str | None = None
    cta_text: str | None = None
    cta_url: str | None = None
    campaign_id: str | None = None
    scheduled_at: datetime | None = None


class AgenteWhatsAppStoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=300)
    media_type: str | None = Field(default=None, pattern="^(image|video)$")
    media_url: str | None = Field(default=None, min_length=2)
    caption: str | None = None
    cta_text: str | None = None
    cta_url: str | None = None
    campaign_id: str | None = None
    scheduled_at: datetime | None = None
    status: str | None = None


class AgenteWhatsAppStoryOut(BaseModel):
    id: str
    campaign_id: str | None
    title: str
    media_type: str
    media_url: str
    caption: str | None
    cta_text: str | None
    cta_url: str | None
    status: str
    scheduled_at: datetime | None
    published_at: datetime | None
    provider_story_id: str | None
    metrics: dict[str, Any]
    created_by: str | None
    created_at: datetime | None
    updated_at: datetime | None


class AgenteWhatsAppStoryPublishOut(BaseModel):
    story_id: str
    status: str
    published: bool


class AgenteWhatsAppStoryTemplateOut(BaseModel):
    id: str
    name: str
    title: str
    caption: str
    cta_text: str | None = None
    cta_url: str | None = None


class AgenteWhatsAppAutomationTemplateOut(BaseModel):
    key: str
    name: str
    description: str
    trigger: str
    cooldown_days: int
    default_message: str


class AgenteWhatsAppAutomationRunIn(BaseModel):
    key: str = Field(..., min_length=3)
    limit: int = Field(default=50, ge=1, le=300)
    dry_run: bool = False
    message_template: str | None = None


class AgenteWhatsAppAutomationCandidateOut(BaseModel):
    customer_id: str
    name: str
    phone: str
    reason: str
    last_order_at: datetime | None = None
    total_orders: int | None = None
    total_spent: float | None = None
    loyalty_points: int | None = None


class AgenteWhatsAppAutomationRunOut(BaseModel):
    key: str
    dry_run: bool
    eligible: int
    queued: int
    skipped: int
    enqueued: int
    candidates: list[AgenteWhatsAppAutomationCandidateOut] = Field(default_factory=list)


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


class AgenteWhatsAppProviderObservabilityOut(BaseModel):
    provider: str
    status: str
    sent: int
    failed: int
    dead: int
    pending: int
    success_rate: float
    avg_send_latency_seconds: float | None
    consecutive_failures: int
    last_failure_at: datetime | None
    last_success_at: datetime | None
    paused_until: datetime | None


class AgenteWhatsAppRecentErrorOut(BaseModel):
    id: str
    status: str
    provider: str
    phone: str
    attempts: int
    error: str | None
    updated_at: datetime | None


class AgenteWhatsAppObservabilityOut(BaseModel):
    health_status: str
    health_message: str
    success_rate: float
    failure_rate: float
    attempted_deliveries: int
    active_alerts: int
    critical_alerts: int
    providers_paused: int
    oldest_pending_age_seconds: int | None
    avg_send_latency_seconds: float | None
    last_sent_at: datetime | None
    last_error_at: datetime | None
    alert_status_counts: dict[str, int]
    providers: list[AgenteWhatsAppProviderObservabilityOut] = Field(default_factory=list)
    recent_errors: list[AgenteWhatsAppRecentErrorOut] = Field(default_factory=list)
    alert_history: list[AgenteWhatsAppInternalAlertOut] = Field(default_factory=list)
