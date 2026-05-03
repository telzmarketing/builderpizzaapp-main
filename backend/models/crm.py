from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from backend.database import Base


class CustomerTag(Base):
    __tablename__ = "customer_tags"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_customer_tags_tenant_slug"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String(100), nullable=False, default="default")
    name = Column(String(120), nullable=False)
    slug = Column(String(140), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(20), nullable=False, default="#f97316")
    status = Column(String(20), nullable=False, default="active")
    source = Column(String(40), nullable=False, default="manual")
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CustomerTagAssignment(Base):
    __tablename__ = "customer_tag_assignments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "customer_id", "tag_id", name="uq_customer_tag_assignment"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String(100), nullable=False, default="default")
    customer_id = Column(String, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    tag_id = Column(String, ForeignKey("customer_tags.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(40), nullable=False, default="manual")
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CustomerSegment(Base):
    __tablename__ = "customer_segments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_customer_segments_tenant_slug"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String(100), nullable=False, default="default")
    name = Column(String(160), nullable=False)
    slug = Column(String(180), nullable=False)
    description = Column(Text, nullable=True)
    rules_json = Column(Text, nullable=False, default="[]")
    status = Column(String(20), nullable=False, default="active")
    source = Column(String(40), nullable=False, default="manual")
    segment_type = Column(String(40), nullable=True)
    refresh_mode = Column(String(30), nullable=False, default="manual")
    last_computed_at = Column(DateTime(timezone=True), nullable=True)
    member_count = Column(Integer, nullable=False, default=0)
    definition_version = Column(Integer, nullable=False, default=1)
    metric_snapshot_json = Column(Text, nullable=False, default="{}")
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CustomerAIProfile(Base):
    __tablename__ = "customer_ai_profiles"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, unique=True)
    profile_summary = Column(Text, nullable=False, default="")
    segment = Column(String(80), nullable=False, default="lead")
    preferences_json = Column(Text, nullable=False, default="{}")
    behavior_json = Column(Text, nullable=False, default="{}")
    churn_risk = Column(String(20), nullable=False, default="low")
    repurchase_probability = Column(Float, nullable=False, default=0.0)
    average_ticket = Column(Float, nullable=False, default=0.0)
    best_contact_day = Column(String(20), nullable=True)
    best_contact_hour = Column(String(20), nullable=True)
    next_best_action = Column(Text, nullable=True)
    recommended_offer = Column(Text, nullable=True)
    recommended_message = Column(Text, nullable=True)
    analysis_source = Column(String(40), nullable=False, default="rules")
    model_version = Column(String(40), nullable=False, default="rules_v1")
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CustomerAISuggestion(Base):
    __tablename__ = "customer_ai_suggestions"
    __table_args__ = (
        UniqueConstraint("customer_id", "suggestion_type", "slug", "status", name="uq_customer_ai_suggestion_status"),
    )

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    suggestion_type = Column(String(20), nullable=False)
    name = Column(String(160), nullable=False)
    slug = Column(String(180), nullable=False)
    reason = Column(Text, nullable=False, default="")
    confidence = Column(String(20), nullable=False, default="medium")
    status = Column(String(20), nullable=False, default="pending")
    target_id = Column(String, nullable=True)
    source = Column(String(40), nullable=False, default="rules")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class CustomerAIAnalysisJob(Base):
    __tablename__ = "customer_ai_analysis_jobs"

    id = Column(String, primary_key=True)
    status = Column(String(20), nullable=False, default="pending")
    total_customers = Column(Integer, nullable=False, default=0)
    processed_customers = Column(Integer, nullable=False, default=0)
    failed_customers = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
