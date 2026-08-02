"""Commercial SaaS platform models built on top of the existing tenant root."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)

from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TenantProfile(Base):
    __tablename__ = "tenant_profiles"

    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    trade_name = Column(String(200), nullable=True)
    tax_id = Column(String(30), nullable=True, index=True)
    state_registration = Column(String(40), nullable=True)
    municipal_registration = Column(String(40), nullable=True)
    segment = Column(String(120), nullable=True)
    website = Column(String(250), nullable=True)
    whatsapp = Column(String(30), nullable=True)
    billing_email = Column(String(200), nullable=True)
    internal_code = Column(String(80), nullable=True)
    logo_url = Column(String(500), nullable=True)
    legal_representative_name = Column(String(200), nullable=True)
    legal_representative_document = Column(String(30), nullable=True)
    legal_representative_email = Column(String(200), nullable=True)
    legal_representative_phone = Column(String(30), nullable=True)
    email = Column(String(200), nullable=True)
    phone = Column(String(30), nullable=True)
    address_line = Column(String(250), nullable=True)
    address_number = Column(String(30), nullable=True)
    address_extra = Column(String(120), nullable=True)
    neighborhood = Column(String(120), nullable=True)
    city = Column(String(120), nullable=True)
    state = Column(String(2), nullable=True)
    postal_code = Column(String(20), nullable=True)
    configuration_status = Column(String(30), nullable=False, default="ready")
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class SaaSPlan(Base):
    __tablename__ = "saas_plans"
    __table_args__ = (
        UniqueConstraint("key", name="uq_saas_plans_key"),
        CheckConstraint("status IN ('active', 'inactive', 'archived')", name="ck_saas_plans_status"),
        CheckConstraint("plan_type IN ('public', 'custom')", name="ck_saas_plans_type"),
        CheckConstraint("billing_cycle IN ('monthly', 'quarterly', 'semiannual', 'annual', 'custom')", name="ck_saas_plans_cycle"),
    )

    id = Column(String, primary_key=True)
    key = Column(String(80), nullable=False)
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    plan_type = Column(String(20), nullable=False, default="public")
    status = Column(String(20), nullable=False, default="active", index=True)
    billing_cycle = Column(String(20), nullable=False, default="monthly")
    currency = Column(String(3), nullable=False, default="BRL")
    grace_period_days = Column(Integer, nullable=False, default=0)
    auto_renew_default = Column(Boolean, nullable=False, default=False)
    price = Column(Numeric(18, 2), nullable=False, default=0)
    monthly_price = Column(Numeric(18, 2), nullable=True)
    quarterly_price = Column(Numeric(18, 2), nullable=True)
    semiannual_price = Column(Numeric(18, 2), nullable=True)
    annual_price = Column(Numeric(18, 2), nullable=True)
    trial_days = Column(Integer, nullable=False, default=0)
    max_users = Column(Integer, nullable=True)
    max_stores = Column(Integer, nullable=True)
    max_orders = Column(Integer, nullable=True)
    max_storage_mb = Column(Integer, nullable=True)
    max_whatsapp_instances = Column(Integer, nullable=True)
    support_level = Column(String(80), nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    archived_at = Column(DateTime(timezone=True), nullable=True)


class SaaSModule(Base):
    __tablename__ = "saas_modules"
    __table_args__ = (
        UniqueConstraint("key", name="uq_saas_modules_key"),
        CheckConstraint(
            "module_group IN ('operation', 'delivery', 'management', 'marketing', 'crm', 'integrations')",
            name="ck_saas_modules_group",
        ),
    )

    id = Column(String, primary_key=True)
    key = Column(String(100), nullable=False)
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    module_group = Column(String(30), nullable=False, index=True)
    active = Column(Boolean, nullable=False, default=True)
    display_order = Column(Integer, nullable=False, default=0)
    dependencies_json = Column(Text, nullable=False, default="[]")
    default_config_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class SaaSPlanModule(Base):
    __tablename__ = "saas_plan_modules"
    __table_args__ = (UniqueConstraint("plan_id", "module_id", name="uq_saas_plan_modules_plan_module"),)

    id = Column(String, primary_key=True)
    plan_id = Column(String, ForeignKey("saas_plans.id", ondelete="CASCADE"), nullable=False)
    module_id = Column(String, ForeignKey("saas_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    limit_value = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"
    __table_args__ = (
        CheckConstraint("status IN ('trial', 'active', 'suspended', 'cancelled')", name="ck_tenant_subscriptions_status"),
        Index("uq_tenant_subscriptions_current", "tenant_id", unique=True, postgresql_where=text("ended_at IS NULL")),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(String, ForeignKey("saas_plans.id", ondelete="RESTRICT"), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="trial")
    custom_terms_json = Column(Text, nullable=False, default="{}")
    starts_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TenantLicense(Base):
    __tablename__ = "tenant_licenses"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_licenses_tenant"),
        CheckConstraint(
            "status IN ('trial', 'active', 'grace_period', 'expired', 'suspended', 'blocked', 'cancelled')",
            name="ck_tenant_licenses_status",
        ),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="trial", index=True)
    starts_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    grace_period_ends_at = Column(DateTime(timezone=True), nullable=True)
    billing_cycle = Column(String(20), nullable=False, default="monthly")
    currency = Column(String(3), nullable=False, default="BRL")
    grace_period_days = Column(Integer, nullable=False, default=0)
    auto_renew = Column(Boolean, nullable=False, default=False)
    contract_value = Column(Numeric(18, 2), nullable=True)
    next_due_at = Column(DateTime(timezone=True), nullable=True)
    suspended_at = Column(DateTime(timezone=True), nullable=True)
    suspension_reason = Column(Text, nullable=True)
    blocked_at = Column(DateTime(timezone=True), nullable=True)
    block_reason = Column(Text, nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TenantLicenseEvent(Base):
    __tablename__ = "tenant_license_events"
    __table_args__ = (Index("ix_tenant_license_events_tenant_created", "tenant_id", "created_at"),)

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    license_id = Column(String, ForeignKey("tenant_licenses.id", ondelete="SET NULL"), nullable=True)
    actor_user_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(50), nullable=False)
    previous_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=False)
    reason = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class TenantModule(Base):
    __tablename__ = "tenant_modules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "module_id", name="uq_tenant_modules_tenant_module"),
        CheckConstraint("origin IN ('plan', 'addon', 'courtesy', 'trial')", name="ck_tenant_modules_origin"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    module_id = Column(String, ForeignKey("saas_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    origin = Column(String(20), nullable=False, default="plan")
    starts_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    limit_value = Column(Integer, nullable=True)
    additional_price = Column(Numeric(18, 2), nullable=False, default=0)
    block_reason = Column(Text, nullable=True)
    config_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TenantBillingProfile(Base):
    __tablename__ = "tenant_billing_profiles"

    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    billing_name = Column(String(200), nullable=True)
    tax_id = Column(String(30), nullable=True)
    email = Column(String(200), nullable=True)
    phone = Column(String(30), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class SaaSInvoice(Base):
    __tablename__ = "saas_invoices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'pending', 'paid', 'overdue', 'cancelled', 'refunded', 'negotiated', 'courtesy')",
            name="ck_saas_invoices_status",
        ),
        CheckConstraint(
            "base_amount >= 0 AND additions_amount >= 0 AND discount_amount >= 0 AND total_amount >= 0",
            name="ck_saas_invoices_amounts",
        ),
        CheckConstraint("period_end > period_start", name="ck_saas_invoices_period"),
        Index("ix_saas_invoices_tenant_status_due", "tenant_id", "status", "due_at"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(String, ForeignKey("saas_plans.id", ondelete="SET NULL"), nullable=True)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    base_amount = Column(Numeric(18, 2), nullable=False, default=0)
    additions_amount = Column(Numeric(18, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(18, 2), nullable=False, default=0)
    total_amount = Column(Numeric(18, 2), nullable=False, default=0)
    due_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    payment_method = Column(String(40), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class SaaSInvoiceItem(Base):
    __tablename__ = "saas_invoice_items"
    __table_args__ = (
        CheckConstraint("quantity > 0 AND unit_amount >= 0 AND total_amount >= 0", name="ck_saas_invoice_items_amounts"),
    )

    id = Column(String, primary_key=True)
    invoice_id = Column(String, ForeignKey("saas_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(String(250), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_amount = Column(Numeric(18, 2), nullable=False)
    total_amount = Column(Numeric(18, 2), nullable=False)
    metadata_json = Column(Text, nullable=False, default="{}")


class SaaSPayment(Base):
    __tablename__ = "saas_payments"
    __table_args__ = (
        CheckConstraint("status IN ('registered', 'confirmed', 'cancelled', 'refunded')", name="ck_saas_payments_status"),
        CheckConstraint("amount > 0", name="ck_saas_payments_amount"),
        Index("ix_saas_payments_tenant_paid", "tenant_id", "paid_at"),
        Index(
            "uq_saas_payments_tenant_reference",
            "tenant_id",
            "reference",
            unique=True,
            postgresql_where=text("reference IS NOT NULL"),
        ),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    invoice_id = Column(String, ForeignKey("saas_invoices.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
    payment_method = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, default="registered")
    paid_at = Column(DateTime(timezone=True), nullable=False)
    reference = Column(String(160), nullable=True)
    notes = Column(Text, nullable=True)
    registered_by = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class SupportSession(Base):
    __tablename__ = "support_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'ended', 'expired', 'revoked')", name="ck_support_sessions_status"),
        Index("ix_support_sessions_actor_status", "actor_user_id", "status"),
        Index("ix_support_sessions_tenant_status", "tenant_id", "status"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    actor_user_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    target_user_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    reason = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="active")
    token_hash = Column(String(64), nullable=False, unique=True)
    starts_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    exchanged_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class TenantInvitation(Base):
    __tablename__ = "tenant_invitations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'revoked')",
            name="ck_tenant_invitations_status",
        ),
        Index("ix_tenant_invitations_tenant_status", "tenant_id", "status"),
        Index("ix_tenant_invitations_email_status", "email", "status"),
        Index(
            "uq_tenant_invitations_pending_email",
            "tenant_id",
            "email",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(200), nullable=False)
    name = Column(String(200), nullable=False)
    phone = Column(String(30), nullable=True)
    job_title = Column(String(120), nullable=True)
    membership_role = Column(String(30), nullable=False, default="viewer")
    role_id = Column(String, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default="pending")
    reason = Column(Text, nullable=False)
    invited_by = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    accepted_by = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    resend_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TenantUsageMetric(Base):
    __tablename__ = "tenant_usage_metrics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "metric_key", "period_key", name="uq_tenant_usage_metric_period"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    metric_key = Column(String(80), nullable=False)
    period_key = Column(String(20), nullable=False)
    value = Column(Float, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TenantInternalNote(Base):
    __tablename__ = "tenant_internal_notes"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
