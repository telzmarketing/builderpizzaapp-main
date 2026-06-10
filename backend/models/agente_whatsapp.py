from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.database import Base


def _now_utc():
    return datetime.now(timezone.utc)


class AgenteWhatsAppSession(Base):
    __tablename__ = "agente_whatsapp_sessions"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    phone = Column(String(30), nullable=False, index=True)
    provider = Column(String(40), nullable=False, default="official")
    provider_contact_id = Column(String(255), nullable=True)
    status = Column(String(30), nullable=False, default="open")
    origin = Column(String(40), nullable=False, default="manual")
    current_intent = Column(String(120), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    assigned_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    ai_enabled = Column(Boolean, nullable=False, default=True)
    automation_blocked = Column(Boolean, nullable=False, default=False)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    customer = relationship("Customer")
    messages = relationship("AgenteWhatsAppMessage", back_populates="session", cascade="all, delete-orphan")
    events = relationship("AgenteWhatsAppEvent", back_populates="session", cascade="all, delete-orphan")
    context = relationship("AgenteWhatsAppContext", back_populates="session", uselist=False, cascade="all, delete-orphan")
    tool_calls = relationship("AgenteWhatsAppToolCall", back_populates="session", cascade="all, delete-orphan")


class AgenteWhatsAppAISettings(Base):
    __tablename__ = "agente_whatsapp_ai_settings"

    id = Column(String, primary_key=True, default="default")
    enabled = Column(Boolean, nullable=False, default=True)
    provider = Column(String(40), nullable=False, default="internal")
    model = Column(String(120), nullable=False, default="internal-rules-v1")
    temperature = Column(Float, nullable=False, default=0.4)
    max_tokens = Column(Integer, nullable=False, default=800)
    prompt_base = Column(Text, nullable=False, default="")
    business_rules = Column(Text, nullable=False, default="")
    tone_of_voice = Column(Text, nullable=False, default="")
    objective = Column(Text, nullable=False, default="")
    transfer_instructions = Column(Text, nullable=False, default="")
    forbidden_topics = Column(Text, nullable=False, default="")
    allowed_tools_json = Column(Text, nullable=False, default="{}")
    openai_api_key = Column(Text, nullable=True)
    anthropic_api_key = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)


class AgenteWhatsAppChannelSettings(Base):
    __tablename__ = "agente_whatsapp_channel_settings"

    id = Column(String, primary_key=True, default="default")
    active_provider = Column(String(40), nullable=False, default="official")
    whatsapp_gateway_instance_id = Column(
        String,
        ForeignKey("whatsapp_gateway_instances.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)


class AgenteWhatsAppMessage(Base):
    __tablename__ = "agente_whatsapp_messages"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("agente_whatsapp_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    direction = Column(String(20), nullable=False)
    sender_type = Column(String(20), nullable=False)
    message_type = Column(String(30), nullable=False, default="text")
    body = Column(Text, nullable=True)
    media_url = Column(Text, nullable=True)
    provider_message_id = Column(String(255), nullable=True, index=True)
    provider_status = Column(String(40), nullable=True)
    error = Column(Text, nullable=True)
    raw_payload_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=_now_utc, index=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    session = relationship("AgenteWhatsAppSession", back_populates="messages")
    customer = relationship("Customer")
    outbox = relationship("AgenteWhatsAppOutbox", back_populates="message", uselist=False, cascade="all, delete-orphan")


class AgenteWhatsAppOutbox(Base):
    __tablename__ = "agente_whatsapp_outbox"

    id = Column(String, primary_key=True)
    message_id = Column(String, ForeignKey("agente_whatsapp_messages.id", ondelete="CASCADE"), nullable=False, unique=True)
    session_id = Column(String, ForeignKey("agente_whatsapp_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    phone = Column(String(30), nullable=False, index=True)
    provider = Column(String(40), nullable=False, default="official")
    status = Column(String(30), nullable=False, default="pending", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    idempotency_key = Column(String(180), nullable=False, unique=True)
    payload_json = Column(Text, nullable=False, default="{}")
    provider_message_id = Column(String(255), nullable=True, index=True)
    error = Column(Text, nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True, index=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc, index=True)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    message = relationship("AgenteWhatsAppMessage", back_populates="outbox")
    session = relationship("AgenteWhatsAppSession")
    customer = relationship("Customer")


class AgenteWhatsAppProviderState(Base):
    __tablename__ = "agente_whatsapp_provider_states"

    id = Column(String, primary_key=True)
    provider = Column(String(40), nullable=False, unique=True, index=True)
    status = Column(String(30), nullable=False, default="active", index=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    failure_threshold = Column(Integer, nullable=False, default=5)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    paused_at = Column(DateTime(timezone=True), nullable=True)
    paused_until = Column(DateTime(timezone=True), nullable=True, index=True)
    paused_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)


class AgenteWhatsAppInternalAlert(Base):
    __tablename__ = "agente_whatsapp_internal_alerts"

    id = Column(String, primary_key=True)
    alert_type = Column(String(80), nullable=False, index=True)
    level = Column(String(30), nullable=False, default="warning", index=True)
    status = Column(String(30), nullable=False, default="active", index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    dedupe_key = Column(String(220), nullable=False, unique=True)
    payload_json = Column(Text, nullable=False, default="{}")
    first_seen_at = Column(DateTime(timezone=True), default=_now_utc)
    last_seen_at = Column(DateTime(timezone=True), default=_now_utc, index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)


class AgenteWhatsAppEvent(Base):
    __tablename__ = "agente_whatsapp_events"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("agente_whatsapp_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    order_id = Column(String, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(100), nullable=False, index=True)
    source = Column(String(80), nullable=False, default="agente_whatsapp")
    payload_json = Column(Text, nullable=False, default="{}")
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc, index=True)

    session = relationship("AgenteWhatsAppSession", back_populates="events")
    customer = relationship("Customer")


class AgenteWhatsAppContext(Base):
    __tablename__ = "agente_whatsapp_context"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("agente_whatsapp_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    short_context_json = Column(Text, nullable=False, default="{}")
    long_context_json = Column(Text, nullable=False, default="{}")
    preferences_json = Column(Text, nullable=False, default="{}")
    behavior_json = Column(Text, nullable=False, default="{}")
    last_intent = Column(String(120), nullable=True)
    sentiment = Column(String(40), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    session = relationship("AgenteWhatsAppSession", back_populates="context")
    customer = relationship("Customer")


class AgenteWhatsAppToolCall(Base):
    __tablename__ = "agente_whatsapp_tool_calls"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("agente_whatsapp_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    tool_name = Column(String(120), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="success")
    arguments_json = Column(Text, nullable=False, default="{}")
    result_json = Column(Text, nullable=False, default="{}")
    error = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=_now_utc, index=True)

    session = relationship("AgenteWhatsAppSession", back_populates="tool_calls")
    customer = relationship("Customer")


class AgenteWhatsAppMetric(Base):
    __tablename__ = "agente_whatsapp_metrics"

    id = Column(String, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    sessions_opened = Column(Integer, nullable=False, default=0)
    messages_inbound = Column(Integer, nullable=False, default=0)
    messages_outbound = Column(Integer, nullable=False, default=0)
    ai_responses = Column(Integer, nullable=False, default=0)
    human_takeovers = Column(Integer, nullable=False, default=0)
    orders_created = Column(Integer, nullable=False, default=0)
    revenue = Column(Float, nullable=False, default=0.0)
    avg_response_time_seconds = Column(Float, nullable=False, default=0.0)
    abandoned_sessions = Column(Integer, nullable=False, default=0)
    recovered_carts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=_now_utc)


class AgenteWhatsAppCampaign(Base):
    __tablename__ = "agente_whatsapp_campaigns"

    id = Column(String, primary_key=True)
    name = Column(String(300), nullable=False)
    status = Column(String(40), nullable=False, default="draft")
    campaign_type = Column(String(60), nullable=False, default="manual")
    audience_json = Column(Text, nullable=False, default="{}")
    template_id = Column(String, nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    sent_count = Column(Integer, nullable=False, default=0)
    delivered_count = Column(Integer, nullable=False, default=0)
    read_count = Column(Integer, nullable=False, default=0)
    replied_count = Column(Integer, nullable=False, default=0)
    conversion_count = Column(Integer, nullable=False, default=0)
    revenue = Column(Float, nullable=False, default=0.0)
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    stories = relationship("AgenteWhatsAppStory", back_populates="campaign")


class AgenteWhatsAppStory(Base):
    __tablename__ = "agente_whatsapp_stories"

    id = Column(String, primary_key=True)
    campaign_id = Column(String, ForeignKey("agente_whatsapp_campaigns.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(300), nullable=False)
    media_type = Column(String(20), nullable=False)
    media_url = Column(Text, nullable=False)
    caption = Column(Text, nullable=True)
    cta_text = Column(String(120), nullable=True)
    cta_url = Column(Text, nullable=True)
    status = Column(String(40), nullable=False, default="draft")
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    provider_story_id = Column(String(255), nullable=True)
    metrics_json = Column(Text, nullable=False, default="{}")
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    campaign = relationship("AgenteWhatsAppCampaign", back_populates="stories")
