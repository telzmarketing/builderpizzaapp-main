"""Validated API contracts for the Master Central."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from backend.schemas.platform_tenant import PlatformTenantCreate, PlatformTenantOut
from backend.schemas.tenant_domain import (
    TenantDomainCreate,
    TenantDomainOut,
    TenantDomainVerificationChallenge,
)


SENSITIVE_CONFIG_KEYS = frozenset({
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "private_key",
    "verification_token",
    "authorization",
    "cookie",
    "client_secret",
    "token_hash",
})


def _validate_public_default_config(value):
    def visit(item) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                normalized = str(key).lower()
                if normalized in SENSITIVE_CONFIG_KEYS or normalized.endswith(
                    ("_password", "_secret", "_token", "_token_hash", "_api_key", "_private_key")
                ):
                    raise ValueError(
                        "default_config nao pode conter credenciais ou segredos"
                    )
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    if value is not None:
        visit(value)
    return value


class TenantProfileIn(BaseModel):
    trade_name: str | None = Field(default=None, max_length=200)
    tax_id: str | None = Field(default=None, max_length=30)
    state_registration: str | None = Field(default=None, max_length=40)
    municipal_registration: str | None = Field(default=None, max_length=40)
    segment: str | None = Field(default=None, max_length=120)
    website: str | None = Field(default=None, max_length=250)
    whatsapp: str | None = Field(default=None, max_length=30)
    billing_email: EmailStr | None = None
    internal_code: str | None = Field(default=None, max_length=80)
    logo_url: str | None = Field(default=None, max_length=500)
    legal_representative_name: str | None = Field(default=None, max_length=200)
    legal_representative_document: str | None = Field(default=None, max_length=30)
    legal_representative_email: EmailStr | None = None
    legal_representative_phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    address_line: str | None = Field(default=None, max_length=250)
    address_number: str | None = Field(default=None, max_length=30)
    address_extra: str | None = Field(default=None, max_length=120)
    neighborhood: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=20)


class TenantOwnerIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    job_title: str | None = Field(default=None, max_length=120)
    password: str = Field(min_length=8, max_length=72)
    force_password_change: bool = True
    # The provisioning wizard always creates a usable owner. Additional users
    # use the dedicated invitation flow, which issues a one-time token.
    status: Literal["active"] = "active"

    @field_validator("password")
    @classmethod
    def bcrypt_safe_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Senha excede o limite seguro de 72 bytes.")
        return value


class TenantWizardIn(BaseModel):
    tenant: PlatformTenantCreate
    owner: TenantOwnerIn
    profile: TenantProfileIn | None = None
    plan_id: str | None = None
    module_ids: list[str] = Field(default_factory=list, max_length=200)
    trial_days: int = Field(default=14, ge=0, le=365)
    billing_cycle: Literal["monthly", "quarterly", "semiannual", "annual", "custom"] = "monthly"
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    grace_period_days: int = Field(default=0, ge=0, le=365)
    auto_renew: bool = False
    initial_status: Literal["active", "suspended", "disabled"] = "active"
    license_starts_at: datetime | None = None
    license_expires_at: datetime | None = None
    contract_value: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    first_due_at: datetime | None = None
    domain: TenantDomainCreate | None = None

    @model_validator(mode="after")
    def validate_license_period(self):
        if (
            self.license_starts_at
            and self.license_expires_at
            and self.license_expires_at <= self.license_starts_at
        ):
            raise ValueError("license_expires_at deve ser posterior a license_starts_at")
        return self


class TenantUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    legal_name: str | None = Field(default=None, max_length=250)
    timezone: str | None = Field(default=None, max_length=80)
    locale: str | None = Field(default=None, max_length=20)
    profile: TenantProfileIn | None = None


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class PlanIn(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,79}$")
    name: str = Field(min_length=2, max_length=160)
    description: str | None = None
    plan_type: Literal["public", "custom"] = "public"
    status: Literal["active", "inactive", "archived"] = "active"
    billing_cycle: Literal["monthly", "quarterly", "semiannual", "annual", "custom"] = "monthly"
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    grace_period_days: int = Field(default=0, ge=0, le=365)
    auto_renew_default: bool = False
    price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    monthly_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    quarterly_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    semiannual_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    annual_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    trial_days: int = Field(default=0, ge=0, le=3650)
    max_users: int | None = Field(default=None, ge=1)
    max_stores: int | None = Field(default=None, ge=1)
    max_orders: int | None = Field(default=None, ge=0)
    max_storage_mb: int | None = Field(default=None, ge=0)
    max_whatsapp_instances: int | None = Field(default=None, ge=0)
    support_level: str | None = Field(default=None, max_length=80)
    display_order: int = Field(default=0, ge=0)
    module_ids: list[str] = Field(default_factory=list)


class PlanUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = None
    plan_type: Literal["public", "custom"] | None = None
    status: Literal["active", "inactive", "archived"] | None = None
    billing_cycle: Literal["monthly", "quarterly", "semiannual", "annual", "custom"] | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    grace_period_days: int | None = Field(default=None, ge=0, le=365)
    auto_renew_default: bool | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    monthly_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    quarterly_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    semiannual_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    annual_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    trial_days: int | None = Field(default=None, ge=0, le=3650)
    max_users: int | None = Field(default=None, ge=1)
    max_stores: int | None = Field(default=None, ge=1)
    max_orders: int | None = Field(default=None, ge=0)
    max_storage_mb: int | None = Field(default=None, ge=0)
    max_whatsapp_instances: int | None = Field(default=None, ge=0)
    support_level: str | None = Field(default=None, max_length=80)
    display_order: int | None = Field(default=None, ge=0)
    module_ids: list[str] | None = None
    reason: str | None = Field(default=None, min_length=3, max_length=1000)

    @model_validator(mode="after")
    def require_reason_for_status_change(self):
        if self.status is not None and not self.reason:
            raise ValueError("reason e obrigatorio ao alterar o status do plano")
        return self


class ModuleIn(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{1,99}$")
    name: str = Field(min_length=2, max_length=160)
    description: str | None = None
    module_group: Literal["operation", "delivery", "management", "marketing", "crm", "integrations"]
    active: bool = True
    display_order: int = Field(default=0, ge=0)
    dependencies: list[str] = Field(default_factory=list)
    default_config: dict = Field(default_factory=dict)

    @field_validator("default_config")
    @classmethod
    def reject_sensitive_default_config(cls, value: dict) -> dict:
        return _validate_public_default_config(value)


class ModuleUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = None
    module_group: Literal["operation", "delivery", "management", "marketing", "crm", "integrations"] | None = None
    active: bool | None = None
    display_order: int | None = Field(default=None, ge=0)
    dependencies: list[str] | None = None
    default_config: dict | None = None
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("default_config")
    @classmethod
    def reject_sensitive_default_config(cls, value: dict | None) -> dict | None:
        return _validate_public_default_config(value)


class TenantModuleItemIn(BaseModel):
    module_id: str
    enabled: bool = True
    origin: Literal["plan", "addon", "courtesy", "trial"] = "plan"
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    limit_value: int | None = Field(default=None, ge=0)
    additional_price: Decimal = Field(default=Decimal("0"), ge=0)
    reason: str | None = Field(default=None, max_length=1000)
    # Omitted/None preserves the encrypted-or-secret-bearing persisted config;
    # an explicit {} remains an intentional clear operation.
    config: dict | None = None

    @model_validator(mode="after")
    def validate_availability_window(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at deve ser posterior a starts_at")
        return self


class TenantModulesUpdateIn(BaseModel):
    modules: list[TenantModuleItemIn]
    reason: str = Field(min_length=3, max_length=1000)


class LicenseActionIn(BaseModel):
    days: int | None = Field(default=None, ge=1, le=3650)
    reason: str = Field(min_length=3, max_length=1000)


class TenantPlanAssignmentIn(BaseModel):
    plan_id: str
    reason: str = Field(min_length=3, max_length=1000)


class InvoiceItemIn(BaseModel):
    description: str = Field(min_length=2, max_length=250)
    quantity: int = Field(default=1, ge=1)
    unit_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)


class InvoiceIn(BaseModel):
    plan_id: str | None = None
    period_start: datetime
    period_end: datetime
    due_at: datetime
    additions_amount: Decimal = Field(default=Decimal("0"), ge=0)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    status: Literal["draft", "pending", "courtesy"] = "draft"
    notes: str | None = None
    items: list[InvoiceItemIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end <= self.period_start:
            raise ValueError("period_end deve ser posterior a period_start")
        return self


class PaymentRegistrationIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    payment_method: str = Field(min_length=2, max_length=40)
    paid_at: datetime
    reference: str | None = Field(default=None, max_length=160)
    notes: str | None = None


class InvoiceDiscountIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    reason: str = Field(min_length=3, max_length=1000)


class InvoiceCourtesyIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class InvoiceExtensionIn(BaseModel):
    due_at: datetime
    reason: str = Field(min_length=3, max_length=1000)


class InvoiceCancellationIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class TenantUserCreateIn(TenantOwnerIn):
    membership_role: Literal["admin", "manager", "operator", "viewer"] = "viewer"
    role_id: str | None = None
    reason: str = Field(min_length=3, max_length=1000)


class TenantUserRoleUpdateIn(BaseModel):
    membership_role: Literal["admin", "manager", "operator", "viewer"]
    role_id: str | None = None
    reason: str = Field(min_length=3, max_length=1000)


class TenantUserStatusIn(BaseModel):
    status: Literal["active", "invited", "suspended", "revoked"]
    reason: str = Field(min_length=3, max_length=1000)


class TenantUserResetPasswordIn(BaseModel):
    password: str = Field(min_length=8, max_length=72)
    force_password_change: bool = True
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("password")
    @classmethod
    def bcrypt_safe_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Senha excede o limite seguro de 72 bytes.")
        return value


class OwnershipTransferIn(BaseModel):
    new_owner_user_id: str
    reason: str = Field(min_length=3, max_length=1000)


class TenantInvitationCreateIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    job_title: str | None = Field(default=None, max_length=120)
    membership_role: Literal["admin", "manager", "operator", "viewer"] = "viewer"
    role_id: str | None = None
    expires_in_hours: int = Field(default=72, ge=1, le=720)
    reason: str = Field(min_length=3, max_length=1000)


class TenantInvitationResendIn(BaseModel):
    expires_in_hours: int = Field(default=72, ge=1, le=720)
    reason: str = Field(min_length=3, max_length=1000)


class TenantInvitationAcceptIn(BaseModel):
    token: str = Field(min_length=32, max_length=500)
    password: str | None = Field(default=None, min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def optional_bcrypt_safe_password(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > 72:
            raise ValueError("Senha excede o limite seguro de 72 bytes.")
        return value


class SupportSessionIn(BaseModel):
    tenant_id: str
    target_user_id: str | None = None
    reason: str = Field(min_length=3, max_length=1000)
    duration_minutes: int = Field(default=30, ge=5, le=120)


class SupportExchangeIn(BaseModel):
    support_token: str = Field(min_length=32, max_length=500)


class DomainActionIn(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class TenantNoteIn(BaseModel):
    note: str = Field(min_length=2, max_length=5000)


class PageOut(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    pages: int


T = TypeVar("T")


class ApiEnvelope(BaseModel, Generic[T]):
    success: bool = True
    data: T
    message: str | None = None


class DashboardMetricOut(BaseModel):
    total_tenants: int
    active_tenants: int
    created_month: int
    total_users: int
    trial_licenses: int
    active_licenses: int
    mrr: Decimal
    overdue_invoices: int
    active_domains: int
    expired_licenses: int
    pending_invoices: int
    domain_errors: int
    user_limits_reached: int


class DashboardAlertOut(BaseModel):
    key: str
    severity: Literal["info", "warning", "critical"]
    title: str
    count: int
    description: str
    tenant_ids: list[str] = Field(default_factory=list)


class DashboardOut(BaseModel):
    tenants: dict
    licenses: dict
    billing: dict
    domains: dict
    generated_at: datetime
    metrics: DashboardMetricOut
    alerts: list[DashboardAlertOut]


class AdminUserPublicOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    active: bool
    phone: str | None = None
    job_title: str | None = None
    role_id: str | None = None
    last_login_at: datetime | None = None
    force_password_change: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TenantMembershipOut(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    role: Literal["owner", "admin", "manager", "operator", "viewer"]
    status: Literal["active", "invited", "suspended", "revoked"]
    is_default: bool
    invited_by: str | None = None
    joined_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TenantUserOut(AdminUserPublicOut):
    membership: TenantMembershipOut


class TenantUserPasswordResetOut(TenantUserOut):
    password_reset: bool = True


class PaymentOut(BaseModel):
    id: str
    tenant_id: str
    invoice_id: str
    amount: Decimal
    payment_method: str
    status: str
    paid_at: datetime
    reference: str | None = None
    notes: str | None = None
    created_at: datetime


class TenantProfileOut(TenantProfileIn):
    tenant_id: str
    configuration_status: str
    metadata_json: str
    created_at: datetime
    updated_at: datetime


class PlanOut(PlanIn):
    id: str
    module_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class ModuleOut(BaseModel):
    id: str
    key: str
    name: str
    description: str | None = None
    module_group: Literal["operation", "delivery", "management", "marketing", "crm", "integrations"]
    active: bool
    display_order: int
    dependencies_json: str
    default_config_json: str | None = None
    config_configured: bool = False
    created_at: datetime
    updated_at: datetime


class TenantModuleOut(BaseModel):
    id: str
    tenant_id: str
    module_id: str
    enabled: bool
    origin: Literal["plan", "addon", "courtesy", "trial"]
    starts_at: datetime
    ends_at: datetime | None = None
    limit_value: int | None = None
    additional_price: Decimal
    block_reason: str | None = None
    config_json: str | None = None
    config_configured: bool = False
    created_at: datetime
    updated_at: datetime


class TenantModuleCatalogItemOut(ModuleOut):
    entitlement: TenantModuleOut | None = None


class LicenseOut(BaseModel):
    id: str
    tenant_id: str
    status: str
    starts_at: datetime
    trial_ends_at: datetime | None = None
    expires_at: datetime | None = None
    grace_period_ends_at: datetime | None = None
    billing_cycle: str
    currency: str
    grace_period_days: int
    auto_renew: bool
    contract_value: Decimal | None = None
    next_due_at: datetime | None = None
    suspended_at: datetime | None = None
    suspension_reason: str | None = None
    blocked_at: datetime | None = None
    block_reason: str | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    days_remaining: int | None = None
    days_used: int | None = None
    ends_at: datetime | None = None
    grace_ends_at: datetime | None = None


class InvoiceOut(BaseModel):
    id: str
    tenant_id: str
    plan_id: str | None = None
    period_start: datetime
    period_end: datetime
    base_amount: Decimal
    additions_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    due_at: datetime
    status: str
    payment_method: str | None = None
    paid_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class PaymentRegistrationOut(BaseModel):
    payment: PaymentOut
    invoice: InvoiceOut
    idempotent_replay: bool = False


class SupportSessionOut(BaseModel):
    id: str
    tenant_id: str
    actor_user_id: str | None = None
    target_user_id: str | None = None
    reason: str
    status: Literal["active", "ended", "expired", "revoked"]
    starts_at: datetime
    expires_at: datetime
    exchanged_at: datetime | None = None
    last_seen_at: datetime | None = None
    ended_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime


class SupportSessionStartOut(BaseModel):
    session: SupportSessionOut
    support_token: str


class SupportExchangeOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    tenant_id: str
    support_session_id: str


class InvitationOut(BaseModel):
    id: str
    tenant_id: str
    email: EmailStr
    name: str
    phone: str | None = None
    job_title: str | None = None
    membership_role: Literal["admin", "manager", "operator", "viewer"]
    role_id: str | None = None
    status: Literal["pending", "accepted", "expired", "revoked"]
    reason: str
    invited_by: str | None = None
    accepted_by: str | None = None
    expires_at: datetime
    sent_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None
    resend_count: int
    created_at: datetime
    updated_at: datetime


class InvitationIssueOut(BaseModel):
    invitation: InvitationOut
    invitation_token: str


class InvitationAcceptOut(BaseModel):
    user: AdminUserPublicOut
    membership: TenantMembershipOut
    tenant_id: str


class AuditLogOut(BaseModel):
    id: str
    tenant_id: str | None = None
    actor_user_id: str | None = None
    actor_label: str
    actor_role: str | None = None
    actor_type: str
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    before_data: str | None = None
    after_data: str | None = None
    reason: str | None = None
    metadata_json: str | None = None
    created_at: datetime


class AuditPageOut(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int
    pages: int


class UsageMetricOut(BaseModel):
    id: str
    tenant_id: str
    metric_key: str
    period_key: str
    value: float
    updated_at: datetime


class ActorSummaryOut(BaseModel):
    id: str
    name: str
    email: EmailStr


class TenantNoteOut(BaseModel):
    id: str
    tenant_id: str
    author_user_id: str | None = None
    note: str
    created_at: datetime
    author: ActorSummaryOut | None = None


class TenantSecurityOut(BaseModel):
    active_users: int
    invited_users: int
    blocked_users: int
    active_support_sessions: int
    support_sessions: list[SupportSessionOut]
    session_revocation_available: bool
    two_factor_available: bool


class TenantSummaryOut(PlatformTenantOut):
    plan: PlanOut | None = None
    license: LicenseOut | None = None
    primary_domain: "TenantDomainOut | None" = None
    trade_name: str | None = None
    document: str | None = None
    responsible: str | None = None
    last_access: datetime | None = None
    days_remaining: int | None = None
    domain_status: Literal[
        "pending", "awaiting_dns", "verifying", "verified", "active",
        "dns_error", "ssl_error", "suspended", "removed",
    ] | None = None
    user_count: int
    users_count: int
    billing_status: Literal["ok", "pending", "overdue"]


class TenantDetailOut(TenantSummaryOut):
    profile: TenantProfileOut | None = None
    modules: list[TenantModuleCatalogItemOut]
    domains: list["TenantDomainOut"]


class TenantPageOut(BaseModel):
    items: list[TenantSummaryOut]
    total: int
    page: int
    page_size: int
    pages: int


class TenantProvisionOut(BaseModel):
    tenant: TenantDetailOut
    owner: AdminUserPublicOut
    license: LicenseOut
    domain: "TenantDomainOut | None" = None
    verification: "TenantDomainVerificationChallenge | None" = None


class TenantMutationOut(PlatformTenantOut):
    pass


class OwnershipTransferOut(BaseModel):
    previous_owner: TenantUserOut
    new_owner: TenantUserOut


class DomainPageOut(BaseModel):
    items: list["TenantDomainOut"]
    total: int
    page: int
    page_size: int
    pages: int


class DomainCreateOut(BaseModel):
    domain: "TenantDomainOut"
    verification: "TenantDomainVerificationChallenge"


class HostSurfaceOut(BaseModel):
    surface: Literal["platform", "store"]
    hostname: str
    tenant_id: str | None = None


class ModuleCatalogSeedOut(BaseModel):
    created_keys: list[str]
    catalog_size: int
    modules: list[ModuleOut]
