from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKeyConstraint, Index, Integer, String, Text, text

from backend.database import Base


def _now_utc():
    return datetime.now(timezone.utc)


class CustomerContactRisk(Base):
    """Current contact-risk projection for one customer and channel."""

    __tablename__ = "customer_contact_risks"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "customer_id"], ["customers.tenant_id", "customers.id"], name="fk_customer_contact_risks_tenant_customer", ondelete="CASCADE"),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_customer_contact_risks_score"),
        CheckConstraint("risk_level IN ('low', 'attention', 'high', 'blocked')", name="ck_customer_contact_risks_level"),
        CheckConstraint("campaign_deliveries_15d >= 0", name="ck_customer_contact_risks_deliveries_15d"),
        CheckConstraint("version >= 1", name="ck_customer_contact_risks_version"),
        Index("uq_customer_contact_risks_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_customer_contact_risks_tenant_customer_channel", "tenant_id", "customer_id", "channel", unique=True),
        Index("ix_customer_contact_risks_tenant_level", "tenant_id", "risk_level"),
        Index("ix_customer_contact_risks_tenant_blocked", "tenant_id", "is_blocked"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False)
    customer_id = Column(String, nullable=False)
    channel = Column(String(40), nullable=False)
    score = Column(Integer, nullable=False, default=0, server_default="0")
    risk_level = Column(String(20), nullable=False, default="low", server_default="low")
    is_blocked = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    block_reason = Column(String(500), nullable=True)
    blocked_at = Column(DateTime(timezone=True), nullable=True)
    campaign_deliveries_15d = Column(Integer, nullable=False, default=0, server_default="0")
    last_event_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now_utc)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now_utc, onupdate=_now_utc)


class CustomerContactRiskEvent(Base):
    """Append-only audit event used to derive a contact-risk projection."""

    __tablename__ = "customer_contact_risk_events"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "customer_id"], ["customers.tenant_id", "customers.id"], name="fk_customer_contact_risk_events_tenant_customer", ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "customer_channel_id"], ["customer_channels.tenant_id", "customer_channels.id"], name="fk_customer_contact_risk_events_tenant_channel"),
        ForeignKeyConstraint(["tenant_id", "risk_id"], ["customer_contact_risks.tenant_id", "customer_contact_risks.id"], name="fk_customer_contact_risk_events_tenant_risk"),
        CheckConstraint("points_delta >= -100 AND points_delta <= 100", name="ck_contact_risk_events_points"),
        CheckConstraint("score_before >= 0 AND score_before <= 100", name="ck_contact_risk_events_before"),
        CheckConstraint("score_after >= 0 AND score_after <= 100", name="ck_contact_risk_events_after"),
        Index("uq_customer_contact_risk_events_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_customer_contact_risk_events_tenant_dedupe", "tenant_id", "dedupe_key", unique=True, postgresql_where=text("dedupe_key IS NOT NULL")),
        Index("ix_customer_contact_risk_events_lookup", "tenant_id", "customer_id", "channel", "occurred_at"),
        Index("ix_customer_contact_risk_events_risk", "tenant_id", "risk_id", "occurred_at"),
        Index("ix_customer_contact_risk_events_source", "tenant_id", "source_type", "source_id"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False)
    customer_id = Column(String, nullable=False)
    customer_channel_id = Column(String, nullable=True)
    risk_id = Column(String, nullable=True)
    channel = Column(String(40), nullable=False)
    event_type = Column(String(50), nullable=False)
    points_delta = Column(Integer, nullable=False)
    score_before = Column(Integer, nullable=False)
    score_after = Column(Integer, nullable=False)
    blocks_contact = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    source_type = Column(String(50), nullable=True)
    source_id = Column(String, nullable=True)
    dedupe_key = Column(String(255), nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=_now_utc)
    metadata_json = Column(Text, nullable=False, default="{}", server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now_utc)
