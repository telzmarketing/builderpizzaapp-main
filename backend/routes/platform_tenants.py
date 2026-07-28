from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.platform_authorization import require_platform_permission
from backend.core.response import ok
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.membership import TenantMembership
from backend.models.tenant import Tenant
from backend.models.tenant_domain import TenantDomain
from backend.schemas.platform_tenant import (
    PlatformTenantCreate,
    PlatformTenantOut,
    PlatformTenantStatusUpdate,
)
from backend.schemas.tenant_domain import TenantDomainCreate, TenantDomainOut
from backend.services.tenant_domain_service import (
    TenantDomainService,
    parse_hostname_set,
    trusted_request_hostname,
)


router = APIRouter(prefix="/admin/platform/tenants", tags=["platform-tenants"])
host_router = APIRouter(prefix="/runtime", tags=["runtime-host"])


@host_router.get("/host-surface")
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
        return ok({"surface": "platform", "hostname": hostname})
    tenant_id = TenantDomainService(db).resolve_active_tenant_id(
        hostname, platform_hostnames=platform_hostnames
    )
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Loja nao encontrada para este dominio.")
    return ok({"surface": "store", "hostname": hostname, "tenant_id": tenant_id})


@router.get("")
def list_tenants(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("tenants.view")),
):
    rows = db.query(Tenant).filter(Tenant.deleted_at.is_(None)).order_by(Tenant.name).all()
    return ok([PlatformTenantOut.model_validate(row) for row in rows])


@router.post("")
def create_tenant(
    body: PlatformTenantCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_platform_permission("tenants.manage")),
):
    if db.query(Tenant.id).filter(Tenant.slug.ilike(body.slug)).first():
        raise HTTPException(status_code=409, detail="Slug de empresa ja cadastrado.")
    tenant = Tenant(
        id=str(uuid.uuid4()),
        slug=body.slug,
        name=body.name.strip(),
        legal_name=body.legal_name.strip() if body.legal_name else None,
        status="active",
        timezone=body.timezone,
        locale=body.locale,
        is_legacy=False,
    )
    has_membership = db.query(TenantMembership.id).filter(
        TenantMembership.user_id == admin.id,
        TenantMembership.status == "active",
    ).first() is not None
    db.add(tenant)
    db.flush()
    db.add(TenantMembership(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        user_id=admin.id,
        role="owner",
        status="active",
        is_default=not has_membership,
        invited_by=admin.id,
        joined_at=datetime.now(timezone.utc),
    ))
    db.commit()
    db.refresh(tenant)
    return ok(PlatformTenantOut.model_validate(tenant))


@router.patch("/{tenant_id}/status")
def update_tenant_status(
    tenant_id: str,
    body: PlatformTenantStatusUpdate,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("tenants.manage")),
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.deleted_at.is_(None)).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Empresa nao encontrada.")
    if tenant.is_legacy and body.status == "disabled":
        raise HTTPException(status_code=409, detail="Empresa legada nao pode ser desativada.")
    tenant.status = body.status
    tenant.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(tenant)
    return ok(PlatformTenantOut.model_validate(tenant))


@router.get("/{tenant_id}/domains")
def list_domains(
    tenant_id: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("tenants.view")),
):
    rows = db.query(TenantDomain).filter(
        TenantDomain.tenant_id == tenant_id
    ).order_by(TenantDomain.created_at.desc()).all()
    return ok([TenantDomainOut.model_validate(row) for row in rows])


@router.post("/{tenant_id}/domains")
def create_domain(
    tenant_id: str,
    body: TenantDomainCreate,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("tenants.manage")),
):
    settings = get_settings()
    try:
        domain, token = TenantDomainService(db).create_pending(
            tenant_id=tenant_id,
            hostname=body.hostname,
            kind=body.kind,
            platform_hostnames=parse_hostname_set(
                settings.TENANT_DOMAINS_PLATFORM_HOSTNAMES
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    db.refresh(domain)
    return ok({
        "domain": TenantDomainOut.model_validate(domain),
        "verification": {
            "record_type": "TXT",
            "record_name": f"_telz-verification.{domain.hostname}",
            "record_value": token,
        },
    })
