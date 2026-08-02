"""Thin HTTP adapters for tenant and Master Central administration."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.platform_authorization import require_platform_permission
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.tenant import Tenant
from backend.schemas.platform_master import (
    ApiEnvelope,
    AuditLogOut,
    AuditPageOut,
    DashboardOut,
    DomainCreateOut,
    DomainPageOut,
    HostSurfaceOut,
    InvitationAcceptOut,
    InvitationIssueOut,
    InvitationOut,
    InvoiceIn,
    InvoiceCancellationIn,
    InvoiceCourtesyIn,
    InvoiceDiscountIn,
    InvoiceExtensionIn,
    InvoiceOut,
    LicenseActionIn,
    LicenseOut,
    ModuleCatalogSeedOut,
    ModuleIn,
    ModuleOut,
    ModuleUpdateIn,
    OwnershipTransferOut,
    PaymentRegistrationIn,
    PaymentRegistrationOut,
    PlanIn,
    PlanOut,
    PlanUpdateIn,
    ReasonIn,
    SupportExchangeIn,
    SupportExchangeOut,
    SupportSessionIn,
    SupportSessionOut,
    SupportSessionStartOut,
    TenantDetailOut,
    TenantInvitationAcceptIn,
    TenantInvitationCreateIn,
    TenantInvitationResendIn,
    TenantModuleCatalogItemOut,
    TenantModulesUpdateIn,
    TenantNoteIn,
    TenantNoteOut,
    TenantPageOut,
    TenantPlanAssignmentIn,
    TenantProvisionOut,
    TenantSecurityOut,
    TenantUserCreateIn,
    TenantUserOut,
    TenantUserPasswordResetOut,
    TenantUserResetPasswordIn,
    TenantUserRoleUpdateIn,
    TenantUserStatusIn,
    TenantUpdateIn,
    TenantWizardIn,
    OwnershipTransferIn,
    UsageMetricOut,
)
from backend.schemas.platform_tenant import PlatformTenantCreate, PlatformTenantOut, PlatformTenantStatusUpdate
from backend.schemas.tenant_domain import TenantDomainCreate, TenantDomainOut
from backend.services.platform_master_service import PlatformMasterService, PlatformNotFound
from backend.services.tenant_domain_service import TenantDomainService, parse_hostname_set, trusted_request_hostname


router = APIRouter(prefix="/admin/platform/tenants", tags=["platform-tenants"])
master_router = APIRouter(prefix="/admin/platform", tags=["platform-master"])
host_router = APIRouter(prefix="/runtime", tags=["runtime-host"])


def _success(data):
    """Return an envelope as data so FastAPI applies the declared response model."""
    return {"success": True, "data": data}


@host_router.get("/host-surface", response_model=ApiEnvelope[HostSurfaceOut])
def host_surface(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    hostname = trusted_request_hostname(
        direct_host=request.headers.get("host"),
        forwarded_host=request.headers.get("x-forwarded-host"),
        remote_addr=request.client.host if request.client else None,
        trust_proxy_headers=settings.TENANT_DOMAINS_TRUST_PROXY_HEADERS,
        trusted_proxy_ips=settings.TENANT_DOMAINS_TRUSTED_PROXY_IPS,
    )
    platform_hostnames = parse_hostname_set(settings.TENANT_DOMAINS_PLATFORM_HOSTNAMES)
    if hostname in platform_hostnames:
        return _success({"surface": "platform", "hostname": hostname})
    tenant_id = TenantDomainService(db).resolve_active_tenant_id(hostname, platform_hostnames=platform_hostnames)
    if tenant_id is None:
        raise PlatformNotFound("Loja nao encontrada para este dominio.", code="DomainHostNotFound")
    return _success({"surface": "store", "hostname": hostname, "tenant_id": tenant_id})


@router.get(
    "",
    response_model=ApiEnvelope[list[PlatformTenantOut] | TenantPageOut],
)
def list_tenants(
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, max_length=30),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    tenant_id: str | None = Query(default=None),
    email: str | None = Query(default=None, max_length=200),
    plan_id: str | None = Query(default=None),
    domain: str | None = Query(default=None, max_length=253),
    billing_status: str | None = Query(default=None, max_length=30),
    module: str | None = Query(default=None, max_length=100),
    expiring_days: int | None = Query(default=None, ge=0, le=3650),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("tenants.view")),
):
    service = PlatformMasterService(db)
    if page is None:
        # Exact backward-compatible shape used by the pre-Central admin screen.
        rows = db.query(Tenant).filter(Tenant.deleted_at.is_(None)).order_by(Tenant.name).all()
        return _success([PlatformTenantOut.model_validate(row) for row in rows])
    return _success(service.list_tenants(page=page, page_size=page_size, q=q, status=status,
        sort_by=sort_by, sort_dir=sort_dir, tenant_id=tenant_id, email=email,
        plan_id=plan_id, domain=domain, billing_status=billing_status,
        module=module, expiring_days=expiring_days))


@router.post(
    "",
    response_model=ApiEnvelope[TenantProvisionOut | PlatformTenantOut],
    status_code=201,
)
def create_tenant(
    body: TenantWizardIn | PlatformTenantCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_platform_permission("tenants.manage")),
):
    service = PlatformMasterService(db)
    if isinstance(body, TenantWizardIn):
        return _success(service.provision(body, actor=admin, request=request,
            platform_hostnames=parse_hostname_set(get_settings().TENANT_DOMAINS_PLATFORM_HOSTNAMES)))
    return _success(PlatformTenantOut.model_validate(
        service.create_legacy_compatible(body, actor=admin, request=request)
    ))


@router.get("/{tenant_id}", response_model=ApiEnvelope[TenantDetailOut])
def tenant_detail(tenant_id: str, db: Session = Depends(get_db),
                  _admin: AdminUser = Depends(require_platform_permission("tenants.view"))):
    return _success(PlatformMasterService(db).detail(tenant_id))


@router.patch("/{tenant_id}", response_model=ApiEnvelope[TenantDetailOut])
def update_tenant(tenant_id: str, body: TenantUpdateIn, request: Request,
                  db: Session = Depends(get_db),
                  admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).update_tenant(tenant_id, body, actor=admin, request=request))


@router.patch("/{tenant_id}/status", response_model=ApiEnvelope[PlatformTenantOut])
def update_tenant_status(tenant_id: str, body: PlatformTenantStatusUpdate, request: Request,
                         db: Session = Depends(get_db),
                         admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).change_tenant_status(
        tenant_id, body.status, reason="Alteracao de status pela Central Master",
        actor=admin, request=request,
    ))


@router.post("/{tenant_id}/suspend", response_model=ApiEnvelope[PlatformTenantOut])
def suspend_tenant(tenant_id: str, body: ReasonIn, request: Request, db: Session = Depends(get_db),
                   admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).change_tenant_status(
        tenant_id, "suspended", reason=body.reason, actor=admin, request=request))


@router.post("/{tenant_id}/reactivate", response_model=ApiEnvelope[PlatformTenantOut])
def reactivate_tenant(tenant_id: str, body: ReasonIn, request: Request, db: Session = Depends(get_db),
                      admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).change_tenant_status(
        tenant_id, "active", reason=body.reason, actor=admin, request=request))


@router.post("/{tenant_id}/archive", response_model=ApiEnvelope[PlatformTenantOut])
def archive_tenant(tenant_id: str, body: ReasonIn, request: Request, db: Session = Depends(get_db),
                   admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).change_tenant_status(
        tenant_id, "archived", reason=body.reason, actor=admin, request=request))


@router.get("/{tenant_id}/users", response_model=ApiEnvelope[list[TenantUserOut]])
def list_tenant_users(tenant_id: str, db: Session = Depends(get_db),
                      _admin: AdminUser = Depends(require_platform_permission("tenants.view"))):
    return _success(PlatformMasterService(db).list_users(tenant_id))


@router.post(
    "/{tenant_id}/users",
    response_model=ApiEnvelope[TenantUserOut],
    status_code=201,
)
def create_tenant_user(tenant_id: str, body: TenantUserCreateIn, request: Request,
                       db: Session = Depends(get_db),
                       admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).create_tenant_user(
        tenant_id, body, actor=admin, request=request))


@router.get(
    "/{tenant_id}/invitations",
    response_model=ApiEnvelope[list[InvitationOut]],
)
def list_tenant_invitations(
    tenant_id: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("tenants.view")),
):
    return _success(PlatformMasterService(db).list_invitations(tenant_id))


@router.post(
    "/{tenant_id}/invitations",
    response_model=ApiEnvelope[InvitationIssueOut],
    status_code=201,
)
def invite_tenant_user(
    tenant_id: str,
    body: TenantInvitationCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_platform_permission("tenants.manage")),
):
    return _success(
        PlatformMasterService(db).invite_tenant_user(
            tenant_id,
            body,
            actor=admin,
            request=request,
        )
    )


@router.post(
    "/{tenant_id}/invitations/{invitation_id}/resend",
    response_model=ApiEnvelope[InvitationIssueOut],
)
def resend_tenant_invitation(
    tenant_id: str,
    invitation_id: str,
    body: TenantInvitationResendIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_platform_permission("tenants.manage")),
):
    return _success(
        PlatformMasterService(db).resend_invitation(
            tenant_id,
            invitation_id,
            body,
            actor=admin,
            request=request,
        )
    )


@master_router.post(
    "/invitations/accept",
    response_model=ApiEnvelope[InvitationAcceptOut],
)
def accept_tenant_invitation(
    body: TenantInvitationAcceptIn,
    request: Request,
    db: Session = Depends(get_db),
):
    return _success(PlatformMasterService(db).accept_invitation(body, request=request))


@router.patch("/{tenant_id}/users/{user_id}/role", response_model=ApiEnvelope[TenantUserOut])
def update_tenant_user_role(tenant_id: str, user_id: str, body: TenantUserRoleUpdateIn,
                            request: Request, db: Session = Depends(get_db),
                            admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).update_tenant_user_role(
        tenant_id, user_id, body, actor=admin, request=request))


@router.patch("/{tenant_id}/users/{user_id}/status", response_model=ApiEnvelope[TenantUserOut])
def update_tenant_user_status(tenant_id: str, user_id: str, body: TenantUserStatusIn,
                              request: Request, db: Session = Depends(get_db),
                              admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).update_tenant_user_status(
        tenant_id, user_id, body, actor=admin, request=request))


@router.post("/{tenant_id}/users/{user_id}/block", response_model=ApiEnvelope[TenantUserOut])
def block_tenant_user(tenant_id: str, user_id: str, body: ReasonIn, request: Request,
                      db: Session = Depends(get_db),
                      admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    payload = TenantUserStatusIn(status="suspended", reason=body.reason)
    return _success(PlatformMasterService(db).update_tenant_user_status(
        tenant_id, user_id, payload, actor=admin, request=request))


@router.post("/{tenant_id}/users/{user_id}/reactivate", response_model=ApiEnvelope[TenantUserOut])
def reactivate_tenant_user(tenant_id: str, user_id: str, body: ReasonIn, request: Request,
                           db: Session = Depends(get_db),
                           admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    payload = TenantUserStatusIn(status="active", reason=body.reason)
    return _success(PlatformMasterService(db).update_tenant_user_status(
        tenant_id, user_id, payload, actor=admin, request=request))


@router.post(
    "/{tenant_id}/users/{user_id}/reset-password",
    response_model=ApiEnvelope[TenantUserPasswordResetOut],
)
def reset_tenant_user_password(tenant_id: str, user_id: str,
                               body: TenantUserResetPasswordIn, request: Request,
                               db: Session = Depends(get_db),
                               admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).reset_tenant_user_password(
        tenant_id, user_id, body, actor=admin, request=request))


@router.post(
    "/{tenant_id}/users/{user_id}/revoke-sessions",
    response_model=ApiEnvelope[TenantUserOut],
)
def revoke_tenant_user_sessions(
    tenant_id: str, user_id: str, body: ReasonIn, request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_platform_permission("tenants.manage")),
):
    return _success(PlatformMasterService(db).revoke_tenant_user_sessions(
        tenant_id, user_id, body, actor=admin, request=request))


@router.post(
    "/{tenant_id}/transfer-ownership",
    response_model=ApiEnvelope[OwnershipTransferOut],
)
def transfer_tenant_ownership(tenant_id: str, body: OwnershipTransferIn, request: Request,
                              db: Session = Depends(get_db),
                              admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).transfer_ownership(
        tenant_id, body, actor=admin, request=request))


@router.get("/{tenant_id}/security", response_model=ApiEnvelope[TenantSecurityOut])
def tenant_security(tenant_id: str, db: Session = Depends(get_db),
                    _admin: AdminUser = Depends(require_platform_permission("tenants.view"))):
    return _success(PlatformMasterService(db).tenant_security(tenant_id))


@router.get("/{tenant_id}/usage", response_model=ApiEnvelope[list[UsageMetricOut]])
def tenant_usage(tenant_id: str, db: Session = Depends(get_db),
                 _admin: AdminUser = Depends(require_platform_permission("tenants.view"))):
    return _success(PlatformMasterService(db).tenant_usage(tenant_id))


@router.post(
    "/{tenant_id}/usage/refresh",
    response_model=ApiEnvelope[list[UsageMetricOut]],
)
def refresh_tenant_usage(
    tenant_id: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("tenants.manage")),
):
    return _success(PlatformMasterService(db).refresh_usage_metrics(tenant_id))


@router.get("/{tenant_id}/notes", response_model=ApiEnvelope[list[TenantNoteOut]])
def tenant_notes(tenant_id: str, db: Session = Depends(get_db),
                 _admin: AdminUser = Depends(require_platform_permission("tenants.view"))):
    return _success(PlatformMasterService(db).notes(tenant_id))


@router.post(
    "/{tenant_id}/notes",
    response_model=ApiEnvelope[TenantNoteOut],
    status_code=201,
)
def add_tenant_note(tenant_id: str, body: TenantNoteIn, request: Request,
                    db: Session = Depends(get_db),
                    admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).add_note(
        tenant_id, body, actor=admin, request=request))


@router.get(
    "/{tenant_id}/modules",
    response_model=ApiEnvelope[list[TenantModuleCatalogItemOut]],
)
def list_tenant_modules(tenant_id: str, db: Session = Depends(get_db),
                        _admin: AdminUser = Depends(require_platform_permission("tenants.view"))):
    return _success(PlatformMasterService(db).list_tenant_modules(tenant_id))


@router.put(
    "/{tenant_id}/modules",
    response_model=ApiEnvelope[list[TenantModuleCatalogItemOut]],
)
def update_tenant_modules(tenant_id: str, body: TenantModulesUpdateIn, request: Request,
                          db: Session = Depends(get_db),
                          admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).update_modules(
        tenant_id, body, actor=admin, request=request))


@router.get("/{tenant_id}/license", response_model=ApiEnvelope[LicenseOut])
def tenant_license(tenant_id: str, db: Session = Depends(get_db),
                   _admin: AdminUser = Depends(require_platform_permission("tenants.view"))):
    return _success(PlatformMasterService(db).license(tenant_id))


@router.put("/{tenant_id}/plan", response_model=ApiEnvelope[TenantDetailOut])
def change_tenant_plan(tenant_id: str, body: TenantPlanAssignmentIn, request: Request,
                       db: Session = Depends(get_db),
                       admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).change_plan(
        tenant_id, body, actor=admin, request=request))


@router.post(
    "/{tenant_id}/license/{action}",
    response_model=ApiEnvelope[LicenseOut],
)
def tenant_license_action(tenant_id: str, action: str, body: LicenseActionIn, request: Request,
                          db: Session = Depends(get_db),
                          admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).license_action(
        tenant_id, action, body, actor=admin, request=request))


@router.get(
    "/{tenant_id}/domains",
    response_model=ApiEnvelope[list[TenantDomainOut]],
)
def list_domains(tenant_id: str, db: Session = Depends(get_db),
                 _admin: AdminUser = Depends(require_platform_permission("tenants.view"))):
    return _success(PlatformMasterService(db).list_tenant_domains(tenant_id))


@router.post(
    "/{tenant_id}/domains",
    response_model=ApiEnvelope[DomainCreateOut],
    status_code=201,
)
def create_domain(tenant_id: str, body: TenantDomainCreate, request: Request,
                  db: Session = Depends(get_db),
                  admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).create_domain(
        tenant_id,
        body,
        actor=admin,
        request=request,
        platform_hostnames=parse_hostname_set(
            get_settings().TENANT_DOMAINS_PLATFORM_HOSTNAMES
        ),
    ))


@master_router.get("/dashboard", response_model=ApiEnvelope[DashboardOut])
def dashboard(db: Session = Depends(get_db),
              _admin: AdminUser = Depends(require_platform_permission("tenants.view"))):
    return _success(PlatformMasterService(db).dashboard())


@master_router.get("/domains", response_model=ApiEnvelope[DomainPageOut])
def all_domains(
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = None, q: str | None = None, db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("tenants.view")),
):
    return _success(PlatformMasterService(db).domain_page(
        page=page,
        page_size=page_size,
        status=status,
        q=q,
    ))


@master_router.post(
    "/domains/{domain_id}/verify",
    response_model=ApiEnvelope[TenantDomainOut],
)
def verify_domain(domain_id: str, request: Request, db: Session = Depends(get_db),
                  admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).domain_action(
        domain_id, "verify", actor=admin, request=request
    ))


@master_router.post(
    "/domains/{domain_id}/activate",
    response_model=ApiEnvelope[TenantDomainOut],
)
def activate_domain(domain_id: str, request: Request, db: Session = Depends(get_db),
                    admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).domain_action(
        domain_id, "activate", actor=admin, request=request
    ))


@master_router.post(
    "/domains/{domain_id}/primary",
    response_model=ApiEnvelope[TenantDomainOut],
)
def primary_domain(domain_id: str, request: Request, db: Session = Depends(get_db),
                   admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).domain_action(
        domain_id, "primary", actor=admin, request=request
    ))


@master_router.post(
    "/domains/{domain_id}/suspend",
    response_model=ApiEnvelope[TenantDomainOut],
)
def suspend_domain(domain_id: str, body: ReasonIn, request: Request, db: Session = Depends(get_db),
                   admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).domain_action(
        domain_id,
        "suspend",
        actor=admin,
        request=request,
        reason=body.reason,
    ))


@master_router.delete(
    "/domains/{domain_id}",
    response_model=ApiEnvelope[TenantDomainOut],
)
def remove_domain(domain_id: str, body: ReasonIn, request: Request, db: Session = Depends(get_db),
                  admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).domain_action(
        domain_id,
        "remove",
        actor=admin,
        request=request,
        reason=body.reason,
    ))


@master_router.get("/plans", response_model=ApiEnvelope[list[PlanOut]])
def list_plans(db: Session = Depends(get_db),
               _admin: AdminUser = Depends(require_platform_permission("tenants.view"))):
    return _success(PlatformMasterService(db).list_plans())


@master_router.post(
    "/plans",
    response_model=ApiEnvelope[PlanOut],
    status_code=201,
)
def create_plan(body: PlanIn, request: Request, db: Session = Depends(get_db),
                admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).create_plan(body, actor=admin, request=request))


@master_router.patch("/plans/{plan_id}", response_model=ApiEnvelope[PlanOut])
def update_plan(plan_id: str, body: PlanUpdateIn, request: Request, db: Session = Depends(get_db),
                admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).update_plan(plan_id, body, actor=admin, request=request))


@master_router.get("/modules", response_model=ApiEnvelope[list[ModuleOut]])
def list_modules(db: Session = Depends(get_db),
                 _admin: AdminUser = Depends(require_platform_permission("tenants.view"))):
    return _success(PlatformMasterService(db).list_modules())


@master_router.post(
    "/modules/seed",
    response_model=ApiEnvelope[ModuleCatalogSeedOut],
)
def seed_modules(
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_platform_permission("tenants.manage")),
):
    return _success(
        PlatformMasterService(db).seed_module_catalog(
            actor=admin,
            request=request,
        )
    )


@master_router.post(
    "/modules",
    response_model=ApiEnvelope[ModuleOut],
    status_code=201,
)
def create_module(body: ModuleIn, request: Request, db: Session = Depends(get_db),
                  admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).create_module(body, actor=admin, request=request))


@master_router.patch(
    "/modules/{module_id}",
    response_model=ApiEnvelope[ModuleOut],
)
def update_module(
    module_id: str,
    body: ModuleUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_platform_permission("tenants.manage")),
):
    return _success(
        PlatformMasterService(db).update_module(
            module_id,
            body,
            actor=admin,
            request=request,
        )
    )


@router.get(
    "/{tenant_id}/invoices",
    response_model=ApiEnvelope[list[InvoiceOut]],
)
def list_invoices(tenant_id: str, db: Session = Depends(get_db),
                  _admin: AdminUser = Depends(require_platform_permission("tenants.view"))):
    return _success(PlatformMasterService(db).list_invoices(tenant_id))


@router.post(
    "/{tenant_id}/invoices",
    response_model=ApiEnvelope[InvoiceOut],
    status_code=201,
)
def create_invoice(tenant_id: str, body: InvoiceIn, request: Request, db: Session = Depends(get_db),
                   admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).create_invoice(
        tenant_id, body, actor=admin, request=request))


@master_router.post(
    "/invoices/{invoice_id}/payments",
    response_model=ApiEnvelope[PaymentRegistrationOut],
    status_code=201,
)
def register_payment(invoice_id: str, body: PaymentRegistrationIn, request: Request,
                     db: Session = Depends(get_db),
                     admin: AdminUser = Depends(require_platform_permission("tenants.manage"))):
    return _success(PlatformMasterService(db).register_payment(
        invoice_id, body, actor=admin, request=request))


@master_router.post(
    "/invoices/{invoice_id}/discount",
    response_model=ApiEnvelope[InvoiceOut],
)
def discount_invoice(
    invoice_id: str,
    body: InvoiceDiscountIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_platform_permission("tenants.manage")),
):
    return _success(
        PlatformMasterService(db).discount_invoice(
            invoice_id, body, actor=admin, request=request
        )
    )


@master_router.post(
    "/invoices/{invoice_id}/courtesy",
    response_model=ApiEnvelope[InvoiceOut],
)
def courtesy_invoice(
    invoice_id: str,
    body: InvoiceCourtesyIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_platform_permission("tenants.manage")),
):
    return _success(
        PlatformMasterService(db).courtesy_invoice(
            invoice_id, body, actor=admin, request=request
        )
    )


@master_router.post(
    "/invoices/{invoice_id}/extend",
    response_model=ApiEnvelope[InvoiceOut],
)
def extend_invoice(
    invoice_id: str,
    body: InvoiceExtensionIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_platform_permission("tenants.manage")),
):
    return _success(
        PlatformMasterService(db).extend_invoice_due_date(
            invoice_id, body, actor=admin, request=request
        )
    )


@master_router.post(
    "/invoices/{invoice_id}/cancel",
    response_model=ApiEnvelope[InvoiceOut],
)
def cancel_invoice(
    invoice_id: str,
    body: InvoiceCancellationIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_platform_permission("tenants.manage")),
):
    return _success(
        PlatformMasterService(db).cancel_invoice(
            invoice_id, body, actor=admin, request=request
        )
    )


@master_router.get(
    "/invoices/{invoice_id}/history",
    response_model=ApiEnvelope[list[AuditLogOut]],
)
def invoice_history(
    invoice_id: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("tenants.view")),
):
    return _success(PlatformMasterService(db).invoice_history(invoice_id))


@master_router.get("/audit-logs", response_model=ApiEnvelope[AuditPageOut])
def audit_logs(page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=100),
               tenant_id: str | None = None, action: str | None = None,
               db: Session = Depends(get_db),
               _admin: AdminUser = Depends(require_platform_permission("audit.view"))):
    return _success(PlatformMasterService(db).audit_page(
        page=page, page_size=page_size, tenant_id=tenant_id, action=action))


@master_router.post(
    "/support-sessions",
    response_model=ApiEnvelope[SupportSessionStartOut],
    status_code=201,
)
def start_support(body: SupportSessionIn, request: Request, db: Session = Depends(get_db),
                  admin: AdminUser = Depends(require_platform_permission("support.impersonate"))):
    return _success(PlatformMasterService(db).start_support(body, actor=admin, request=request))


@master_router.post(
    "/support-sessions/exchange",
    response_model=ApiEnvelope[SupportExchangeOut],
)
def exchange_support_session(
    body: SupportExchangeIn,
    request: Request,
    db: Session = Depends(get_db),
):
    return _success(
        PlatformMasterService(db).exchange_support_token(body, request=request)
    )


@master_router.post(
    "/support-sessions/{session_id}/end",
    response_model=ApiEnvelope[SupportSessionOut],
)
def end_support(session_id: str, request: Request, db: Session = Depends(get_db),
                admin: AdminUser = Depends(require_platform_permission("support.impersonate"))):
    return _success(PlatformMasterService(db).end_support(session_id, actor=admin, request=request))
