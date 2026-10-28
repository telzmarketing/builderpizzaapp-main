"""Pydantic contracts for the administrative Gestor foundation."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GestorContactCreate(BaseModel):
    admin_user_id: UUID
    phone: str = Field(min_length=8, max_length=32)
    display_name: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=80)
    active: bool = True
    requires_reauth: bool = True


class GestorContactUpdate(BaseModel):
    phone: str | None = Field(default=None, min_length=8, max_length=32)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = Field(default=None, min_length=1, max_length=80)
    active: bool | None = None
    requires_reauth: bool | None = None


class GestorContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    admin_user_id: UUID
    phone_normalized: str
    display_name: str
    role: str
    active: bool
    requires_reauth: bool
    created_at: datetime
    updated_at: datetime


class GestorOperationPreviewIn(BaseModel):
    channel: str = Field(min_length=1, max_length=40)
    phone: str = Field(min_length=8, max_length=32)
    tool_name: str = Field(min_length=1, max_length=120)
    risk_level: str = Field(min_length=1, max_length=20)
    arguments: dict[str, Any] = Field(default_factory=dict)
    preview: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    confirmation_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    reauthenticated: bool = False


class GestorOperationConfirmIn(BaseModel):
    confirmation_token: str = Field(min_length=16, max_length=256)


class GestorOperationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel: str
    phone: str
    tool_name: str
    risk_level: str
    status: str
    arguments: dict[str, Any]
    preview: dict[str, Any]
    idempotency_key: str
    confirmation_expires_at: datetime | None
    executed_at: datetime | None
    error: str | None
    result: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class GestorOperationPreviewOut(BaseModel):
    operation: GestorOperationOut
    confirmation_token: str
    execution_note: str


class GestorToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GestorBIDashboardArguments(GestorToolArguments):
    period: Literal["7d", "30d", "90d"] = "30d"


class GestorInventoryOverviewArguments(GestorToolArguments):
    pass


class GestorFinanceOverviewArguments(GestorToolArguments):
    pass


class GestorOperationsSummaryArguments(GestorToolArguments):
    pass


class GestorFiscalOverviewArguments(GestorToolArguments):
    pass


class GestorLogisticsSummaryArguments(GestorToolArguments):
    pass


class GestorProductsCatalogArguments(GestorToolArguments):
    active_only: bool = True
    channel: Literal["delivery", "dine_in"] = "delivery"


class GestorCRMSummaryArguments(GestorToolArguments):
    pass


class GestorProductUpdatePriceArguments(GestorToolArguments):
    product_id: str = Field(min_length=1, max_length=200)
    price: float = Field(ge=0)
    delivery_price: float | None = Field(default=None, ge=0)
    dine_in_price: float | None = Field(default=None, ge=0)


class GestorFinanceCreateExpenseArguments(GestorToolArguments):
    account_id: str | None = None
    category_id: str | None = None
    counterparty_id: str | None = None
    description: str = Field(min_length=1, max_length=220)
    amount: float = Field(gt=0)
    competence_date: str = Field(min_length=10, max_length=10)
    due_date: str | None = Field(default=None, min_length=10, max_length=10)
    notes: str | None = None


class GestorCRMCreateTaskArguments(GestorToolArguments):
    title: str = Field(min_length=1, max_length=300)
    customer_id: str | None = None
    card_id: str | None = None
    description: str | None = None
    task_type: str = Field(default="other", max_length=50)
    responsible: str | None = None
    due_date: str | None = None
    priority: str = Field(default="medium", max_length=20)


class GestorInventoryManualEntryArguments(GestorToolArguments):
    item_id: str = Field(min_length=1, max_length=200)
    location_id: str | None = None
    movement_type: Literal["in", "out", "adjustment"] = "in"
    quantity: float = Field(gt=0)
    unit_cost: float = Field(default=0, ge=0)
    reason: str = Field(default="manual", min_length=1, max_length=120)
    notes: str | None = None


class GestorOrderStatusUpdateArguments(GestorToolArguments):
    order_id: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=40)
    changed_by: str = Field(default="gestor", min_length=1, max_length=120)


class GestorInventoryApproveReceiptArguments(GestorToolArguments):
    document_id: str = Field(min_length=1, max_length=200)


class GestorInventoryApproveReceiptResult(BaseModel):
    id: str | None = None
    status: str | None = None
    document_id: str | None = None
    tenant_id: str | None = None
    model_config = ConfigDict(extra="allow")


class GestorToolResult(BaseModel):
    model_config = ConfigDict(extra="allow")


class GestorToolExecuteIn(BaseModel):
    tool_name: str = Field(min_length=1, max_length=120)
    arguments: dict[str, Any] = Field(default_factory=dict)
    operation_id: str | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    channel: str = Field(default="gestor", min_length=1, max_length=40)
    phone: str = Field(min_length=8, max_length=32)
    reauthenticated: bool = False


class GestorToolCatalogItem(BaseModel):
    name: str
    description: str
    module: str
    risk_level: Literal["low", "medium", "high"]
    mutates_data: bool = False
    requires_confirmation: bool = False
    evidence_required: list[str] = Field(default_factory=list)
    reauth_required: bool = False
    available: bool = True
    unavailable_reason: str | None = None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class GestorToolExecuteOut(BaseModel):
    operation: GestorOperationOut
    result: dict[str, Any] | None = None


class GestorAISettingsUpdate(BaseModel):
    enabled: bool | None = None
    provider: Literal["internal", "openai", "claude"] | None = None
    model: str | None = Field(default=None, min_length=1, max_length=120)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=100000)
    system_instructions: str | None = Field(default=None, max_length=20000)
    operational_rules: str | None = Field(default=None, max_length=20000)
    monthly_token_limit: int | None = Field(default=None, ge=0, le=1000000000)
    monthly_cost_limit: float | None = Field(default=None, ge=0, le=1000000000)
    writes_enabled: bool | None = None


class GestorAISettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    enabled: bool
    provider: Literal["internal", "openai", "claude"]
    model: str
    temperature: float
    max_tokens: int
    system_instructions: str
    operational_rules: str
    monthly_token_limit: int
    monthly_cost_limit: float
    writes_enabled: bool
    updated_at: datetime


class GestorAIProviderStatusOut(BaseModel):
    provider: Literal["internal", "openai", "claude"]
    configured: bool
    enabled: bool
    model: str
    openai_configured: bool
    claude_configured: bool
    openai_key_preview: str | None = None
    claude_key_preview: str | None = None


class GestorAIPlanIn(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=200)
    channel: Literal["gestor"] = "gestor"


class GestorAIProposedTool(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    risk_level: Literal["low", "medium", "high"]
    requires_confirmation: bool
    summary: str
    evidence_required: list[str] = Field(default_factory=list)


class GestorAIUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


class GestorAIPlanOut(BaseModel):
    provider: Literal["internal", "openai", "claude"]
    model: str
    response_text: str
    proposed_tools: list[GestorAIProposedTool] = Field(default_factory=list)
    no_execution: Literal[True] = True
    usage: GestorAIUsage


class GestorAIProviderPlanTool(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1, max_length=120)
    arguments: dict[str, Any] = Field(default_factory=dict)
    summary: str = Field(min_length=1, max_length=2000)
    evidence_required: list[str] = Field(default_factory=list, max_length=20)


class GestorAIProviderPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_text: str = Field(max_length=20000)
    proposed_tools: list[GestorAIProviderPlanTool] = Field(default_factory=list, max_length=20)


class GestorWhatsAppChannelUpdate(BaseModel):
    enabled: bool | None = None
    phone_number_id: str | None = Field(default=None, min_length=1, max_length=120)
    business_account_id: str | None = Field(default=None, min_length=1, max_length=120)
    display_phone_number: str | None = Field(default=None, max_length=40)
    verify_token: str | None = Field(default=None, min_length=16, max_length=512)
    app_secret_ref: str | None = Field(default=None, min_length=1, max_length=200)
    access_token_ref: str | None = Field(default=None, min_length=1, max_length=200)
    integration_connection_id: UUID | None = None


class GestorWhatsAppChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    enabled: bool
    phone_number_id: str
    business_account_id: str
    display_phone_number: str | None
    app_secret_ref: str
    access_token_ref: str | None
    integration_connection_id: UUID | None
    status: str
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class GestorWhatsAppWebhookOut(BaseModel):
    accepted: bool
    tenant_id: UUID
    channel_id: UUID
    received: int
    duplicates: int
    status: Literal["RECEIVED"] = "RECEIVED"


class GestorWhatsAppMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    channel_id: UUID
    provider_message_id: str
    from_phone: str
    message_type: str
    text_body: str | None
    payload_json: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class GestorInboxProcessOut(BaseModel):
    processed: int
    planned: int
    responded: int
    rejected: int
    failed: int
    skipped: int


class GestorWhatsAppSendMessageArguments(GestorToolArguments):
    """Arguments kept inside a confirmed Gestor operation, never in a secret field."""

    to_phone: str = Field(min_length=8, max_length=32)
    message_type: Literal["text", "template"] = "text"
    body: str | None = Field(default=None, max_length=4096)
    template_name: str | None = Field(default=None, min_length=1, max_length=200)
    template_language: str = Field(default="pt_BR", min_length=2, max_length=20)
    template_variables: list[str] = Field(default_factory=list, max_length=20)


class GestorWhatsAppEnqueueIn(BaseModel):
    operation_id: UUID


class GestorWhatsAppOutboxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    operation_id: UUID
    recipient_phone: str
    message_type: Literal["text", "template"]
    body: str | None
    template_name: str | None
    template_language: str | None
    template_variables: list[str]
    idempotency_key: str
    status: str
    attempts: int
    max_attempts: int
    provider_message_id: str | None
    error: str | None
    next_attempt_at: datetime | None
    locked_at: datetime | None
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GestorWhatsAppEnqueueOut(BaseModel):
    outbox: GestorWhatsAppOutboxOut
    idempotent_replay: bool = False
    policy: dict[str, Any]


class GestorWhatsAppOutboxProcessOut(BaseModel):
    processed: int
    sent: int
    failed: int
    deferred: int
    dead: int


class GestorWhatsAppOutboxRetryOut(BaseModel):
    outbox: GestorWhatsAppOutboxOut


class GestorMultimodalIn(BaseModel):
    """Inline multimodal intake; binary content is base64 and never a URL."""
    media_type: Literal["text", "image", "audio", "document"]
    mime_type: str | None = Field(default=None, max_length=120)
    filename: str | None = Field(default=None, max_length=255)
    text: str | None = Field(default=None, max_length=200000)
    content_base64: str | None = Field(default=None, max_length=30000000)
    idempotency_key: str = Field(min_length=1, max_length=220)
    source_message_id: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GestorMultimodalReviewIn(BaseModel):
    approved: bool
    extracted_text: str | None = Field(default=None, max_length=200000)
    note: str | None = Field(default=None, max_length=2000)


class GestorMultimodalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    media_type: Literal["text", "image", "audio", "document"]
    mime_type: str
    original_filename: str | None
    size_bytes: int
    content_sha256: str
    storage_key: str | None
    idempotency_key: str
    status: str
    review_required: bool
    review_reason: str | None
    extracted_text: str | None
    confidence: float | None
    processor: str | None
    source_message_id: str | None
    metadata_json: dict[str, Any]
    error: str | None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None


class GestorMultimodalIngestOut(BaseModel):
    artifact: GestorMultimodalOut
    idempotent_replay: bool = False


class GestorMultimodalAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    artifact_id: UUID
    event: str
    status: str
    details_json: dict[str, Any]
    created_at: datetime


class GestorAutomationCondition(BaseModel):
    key: str = "field"
    field: str = Field(min_length=1, max_length=120)
    operator: Literal["eq", "neq", "in", "gt", "gte", "lt", "lte", "contains", "exists"]
    value: Any = None


class GestorAutomationAction(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    config: dict[str, Any] = Field(default_factory=dict)


class GestorAutomationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    trigger_key: str = Field(min_length=1, max_length=80)
    conditions: list[GestorAutomationCondition] = Field(default_factory=list)
    actions: list[GestorAutomationAction] = Field(min_length=1, max_length=10)
    enabled: bool = False
    dry_run: bool = True
    max_runs_per_hour: int = Field(default=10, ge=1, le=1000)
    daily_cost_limit: int = Field(default=100, ge=1, le=100000)
    daily_quantity_limit: int = Field(default=100, ge=1, le=100000)
    max_actions_per_event: int = Field(default=5, ge=1, le=10)
    service_window_start: str = Field(default="08:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    service_window_end: str = Field(default="22:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    service_weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6], min_length=1, max_length=7)
    opt_out_required: bool = True


class GestorAutomationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    trigger_key: str | None = Field(default=None, min_length=1, max_length=80)
    conditions: list[GestorAutomationCondition] | None = None
    actions: list[GestorAutomationAction] | None = Field(default=None, min_length=1, max_length=10)
    enabled: bool | None = None
    dry_run: bool | None = None
    max_runs_per_hour: int | None = Field(default=None, ge=1, le=1000)
    daily_cost_limit: int | None = Field(default=None, ge=1, le=100000)
    daily_quantity_limit: int | None = Field(default=None, ge=1, le=100000)
    max_actions_per_event: int | None = Field(default=None, ge=1, le=10)
    service_window_start: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    service_window_end: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    service_weekdays: list[int] | None = Field(default=None, min_length=1, max_length=7)
    opt_out_required: bool | None = None


class GestorAutomationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    trigger_key: str
    conditions: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    enabled: bool
    dry_run: bool
    max_runs_per_hour: int
    daily_cost_limit: int
    daily_quantity_limit: int
    max_actions_per_event: int
    service_window_start: str
    service_window_end: str
    service_weekdays: list[int]
    opt_out_required: bool
    created_at: datetime
    updated_at: datetime


class GestorAutomationSimulateIn(BaseModel):
    event_key: str | None = Field(default=None, max_length=80)
    event_id: str | None = Field(default=None, max_length=120)
    payload: dict[str, Any] = Field(default_factory=dict)


class GestorAutomationSimulationOut(BaseModel):
    automation_id: UUID
    matched: bool
    would_queue: bool
    blocked_reason: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    dry_run: bool


class GestorAutomationRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    automation_id: UUID
    event_id: str
    status: str
    action_count: int
    cost_units: int
    operation_ids: list[str]
    details: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class GestorAutomationProcessOut(BaseModel):
    claimed: int
    processed: int
    previews: int
    awaiting_confirmation: int
    skipped: int
    failed: int
    idempotent_replays: int
    runs: list[GestorAutomationRunOut] = Field(default_factory=list)
    confirmation_tokens: dict[str, str] = Field(default_factory=dict)
