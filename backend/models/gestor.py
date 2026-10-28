"""Tenant-scoped persistence for the administrative Gestor foundation."""
from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, Text, UniqueConstraint

from backend.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class GestorAuthorizedContact(Base):
    __tablename__ = "gestor_authorized_contacts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "phone_normalized", name="uq_gestor_contacts_tenant_phone"),
        ForeignKeyConstraint(
            ["tenant_id", "admin_user_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.user_id"],
            name="fk_gestor_contacts_tenant_admin_membership",
            ondelete="RESTRICT",
        ),
        Index("ix_gestor_contacts_tenant_active", "tenant_id", "active"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    admin_user_id = Column(String, ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False)
    phone_normalized = Column(String(32), nullable=False)
    display_name = Column(String(200), nullable=False)
    role = Column(String(80), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    requires_reauth = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class GestorOperation(Base):
    __tablename__ = "gestor_operations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_gestor_operations_tenant_idempotency"),
        Index("ix_gestor_operations_tenant_status_created", "tenant_id", "status", "created_at"),
        Index("ix_gestor_operations_tenant_created", "tenant_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    requested_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    channel = Column(String(40), nullable=False)
    phone = Column(String(32), nullable=False)
    tool_name = Column(String(120), nullable=False)
    risk_level = Column(String(20), nullable=False)
    status = Column(String(32), nullable=False, default="PENDING_CONFIRMATION")
    arguments_json = Column(JSON, nullable=False, default=dict)
    preview_json = Column(JSON, nullable=False, default=dict)
    idempotency_key = Column(String(200), nullable=False)
    confirmation_token_hash = Column(String(128), nullable=True)
    confirmation_expires_at = Column(DateTime(timezone=True), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class GestorAISettings(Base):
    """Tenant-scoped planner configuration; provider credentials live in secrets."""
    __tablename__ = "gestor_ai_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_gestor_ai_settings_tenant"),
        Index("ix_gestor_ai_settings_tenant", "tenant_id"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    provider = Column(String(20), nullable=False, default="internal")
    model = Column(String(120), nullable=False, default="internal-rules-v1")
    temperature = Column(Float, nullable=False, default=0.2)
    max_tokens = Column(Integer, nullable=False, default=800)
    system_instructions = Column(Text, nullable=False, default="")
    operational_rules = Column(Text, nullable=False, default="")
    monthly_token_limit = Column(Integer, nullable=False, default=0)
    monthly_cost_limit = Column(Float, nullable=False, default=0.0)
    writes_enabled = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class GestorWhatsAppChannel(Base):
    """Official Meta channel for administrative Gestor traffic only."""
    __tablename__ = "gestor_whatsapp_channels"
    __table_args__ = (
        UniqueConstraint("phone_number_id", name="uq_gestor_whatsapp_phone_number_id"),
        UniqueConstraint("tenant_id", name="uq_gestor_whatsapp_tenant_channel"),
        Index("ix_gestor_whatsapp_channels_tenant_status", "tenant_id", "status"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    enabled = Column(Boolean, nullable=False, default=False)
    phone_number_id = Column(String(120), nullable=False)
    business_account_id = Column(String(120), nullable=False)
    display_phone_number = Column(String(40), nullable=True)
    verify_token_hash = Column(String(128), nullable=False)
    app_secret_ref = Column(String(200), nullable=False)
    # External secret-manager reference only. The bearer token itself is never
    # persisted in the Gestor schema or returned by an API response.
    access_token_ref = Column(String(200), nullable=True)
    # Kept as an optional reference because IntegrationConnection is declared
    # in the legacy marketing route module; the Alembic schema enforces the FK.
    integration_connection_id = Column(String, nullable=True)
    status = Column(String(32), nullable=False, default="pending_secret")
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class GestorWhatsAppMessage(Base):
    """Durable, non-executing inbox for messages received on the Gestor channel."""
    __tablename__ = "gestor_whatsapp_messages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_message_id", name="uq_gestor_whatsapp_message_provider"),
        Index("ix_gestor_whatsapp_messages_channel_status", "channel_id", "status", "created_at"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(String, ForeignKey("gestor_whatsapp_channels.id", ondelete="CASCADE"), nullable=False)
    provider_message_id = Column(String(255), nullable=False)
    from_phone = Column(String(32), nullable=False)
    message_type = Column(String(40), nullable=False)
    text_body = Column(Text, nullable=True)
    payload_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(24), nullable=False, default="RECEIVED")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class GestorWhatsAppOutbox(Base):
    """Isolated asynchronous outbound queue for administrative Gestor traffic."""
    __tablename__ = "gestor_whatsapp_outbox"
    __table_args__ = (
        UniqueConstraint("tenant_id", "operation_id", name="uq_gestor_whatsapp_outbox_operation"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_gestor_whatsapp_outbox_idempotency"),
        Index("ix_gestor_whatsapp_outbox_tenant_status_due", "tenant_id", "status", "next_attempt_at"),
        Index("ix_gestor_whatsapp_outbox_channel_created", "channel_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(String, ForeignKey("gestor_whatsapp_channels.id", ondelete="CASCADE"), nullable=False)
    operation_id = Column(String, ForeignKey("gestor_operations.id", ondelete="CASCADE"), nullable=False)
    recipient_phone = Column(String(32), nullable=False)
    message_type = Column(String(20), nullable=False, default="text")
    body = Column(Text, nullable=True)
    template_name = Column(String(200), nullable=True)
    template_language = Column(String(20), nullable=True)
    template_variables = Column(JSON, nullable=False, default=list)
    idempotency_key = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    provider_message_id = Column(String(255), nullable=True)
    error = Column(Text, nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class GestorMultimodalArtifact(Base):
    """Tenant-owned multimodal input and its safe processing projection."""
    __tablename__ = "gestor_multimodal_artifacts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_gestor_multimodal_tenant_idempotency"),
        Index("ix_gestor_multimodal_tenant_status_created", "tenant_id", "status", "created_at"),
        Index("ix_gestor_multimodal_tenant_hash", "tenant_id", "content_sha256"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    uploaded_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    storage_asset_id = Column(String(32), ForeignKey("tenant_upload_assets.id", ondelete="SET NULL"), nullable=True)
    media_type = Column(String(20), nullable=False)
    mime_type = Column(String(120), nullable=False)
    original_filename = Column(String(255), nullable=True)
    size_bytes = Column(Integer, nullable=False, default=0)
    content_sha256 = Column(String(64), nullable=False)
    storage_key = Column(String(700), nullable=True)
    idempotency_key = Column(String(220), nullable=False)
    status = Column(String(30), nullable=False, default="received")
    review_required = Column(Boolean, nullable=False, default=False)
    review_reason = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    processor = Column(String(80), nullable=True)
    source_message_id = Column(String(255), nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    processed_at = Column(DateTime(timezone=True), nullable=True)


class GestorMultimodalAudit(Base):
    """Append-only audit events for multimodal ingestion and review."""
    __tablename__ = "gestor_multimodal_audits"
    __table_args__ = (
        Index("ix_gestor_multimodal_audits_tenant_created", "tenant_id", "created_at"),
        Index("ix_gestor_multimodal_audits_artifact_created", "artifact_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    artifact_id = Column(String, ForeignKey("gestor_multimodal_artifacts.id", ondelete="CASCADE"), nullable=False)
    actor_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    event = Column(String(60), nullable=False)
    status = Column(String(30), nullable=False)
    details_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class GestorAutomation(Base):
    """Tenant-scoped proactive rules backed by the transversal event stream."""
    __tablename__ = "gestor_automations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_gestor_automations_tenant_name"),
        Index("ix_gestor_automations_tenant_enabled_trigger", "tenant_id", "enabled", "trigger_key"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    created_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    updated_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    trigger_key = Column(String(80), nullable=False)
    conditions_json = Column(JSON, nullable=False, default=list)
    actions_json = Column(JSON, nullable=False, default=list)
    enabled = Column(Boolean, nullable=False, default=False)
    dry_run = Column(Boolean, nullable=False, default=True)
    max_runs_per_hour = Column(Integer, nullable=False, default=10)
    daily_cost_limit = Column(Integer, nullable=False, default=100)
    daily_quantity_limit = Column(Integer, nullable=False, default=100)
    max_actions_per_event = Column(Integer, nullable=False, default=5)
    service_window_start = Column(String(5), nullable=False, default="08:00")
    service_window_end = Column(String(5), nullable=False, default="22:00")
    service_weekdays_json = Column(JSON, nullable=False, default=lambda: [0, 1, 2, 3, 4, 5, 6])
    opt_out_required = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class GestorAutomationRun(Base):
    """Idempotent materialization of one Gestor automation against one event."""
    __tablename__ = "gestor_automation_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "automation_id", "event_id", name="uq_gestor_automation_runs_event"),
        Index("ix_gestor_automation_runs_tenant_status_created", "tenant_id", "status", "created_at"),
        Index("ix_gestor_automation_runs_tenant_automation_created", "tenant_id", "automation_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    automation_id = Column(String, ForeignKey("gestor_automations.id", ondelete="CASCADE"), nullable=False)
    event_id = Column(String, nullable=False)
    status = Column(String(32), nullable=False, default="preview")
    action_count = Column(Integer, nullable=False, default=0)
    cost_units = Column(Integer, nullable=False, default=0)
    operation_ids_json = Column(JSON, nullable=False, default=list)
    details_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class GestorAutomationAudit(Base):
    """Append-only operational audit for Gestor automation changes and runs."""
    __tablename__ = "gestor_automation_audits"
    __table_args__ = (
        Index("ix_gestor_automation_audits_tenant_created", "tenant_id", "created_at"),
        Index("ix_gestor_automation_audits_automation_created", "automation_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    automation_id = Column(String, ForeignKey("gestor_automations.id", ondelete="CASCADE"), nullable=False)
    run_id = Column(String, ForeignKey("gestor_automation_runs.id", ondelete="SET NULL"), nullable=True)
    actor_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    event = Column(String(60), nullable=False)
    status = Column(String(32), nullable=False)
    details_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
