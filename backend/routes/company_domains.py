"""Company domain APIs require both current membership and tenant-scoped RBAC."""
from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import ConfigDict
from sqlalchemy.orm import Session

from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.tenant_auth import get_current_tenant_context
from backend.core.tenant_context import TenantContext, TenantSource
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin
from backend.schemas.platform_master import ApiEnvelope, DomainCreateOut
from backend.schemas.tenant_domain import TenantDomainCreate, TenantDomainOut
from backend.schemas.tenant_domain_ssl import CertificateRequestIn, CertificateSummaryOut
from backend.services.tenant_domain_self_service import TenantDomainSelfService


router = APIRouter(prefix="/admin/company/domains", tags=["company-domains"])


class CompanyDomainCreate(TenantDomainCreate):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class CompanyDomainActor:
    admin: AdminUser
    context: TenantContext


def company_domain_actor(permission):
    def dependency(
        context: TenantContext = Depends(get_current_tenant_context),
        actor: AuthorizedTenantActor = Depends(require_rbac_permission("configuracoes", permission)),
        admin: AdminUser = Depends(get_current_admin),
    ):
        if (context.source != TenantSource.PANEL or actor.tenant_context.source != TenantSource.PANEL
                or context.actor_id != admin.id or actor.user_id != admin.id
                or actor.tenant_id != context.tenant_id
                or actor.tenant_context.tenant_id != context.tenant_id
                or actor.tenant_context.actor_id != context.actor_id
                or actor.tenant_context.membership_id != context.membership_id):
            raise HTTPException(status_code=403, detail="Gestao de dominios exige permissoes da empresa selecionada.")
        return CompanyDomainActor(admin=admin, context=context)
    return dependency


view_actor = company_domain_actor("view")
edit_actor = company_domain_actor("edit")


@router.get("", response_model=ApiEnvelope[list[TenantDomainOut]])
def list_domains(db: Session = Depends(get_db), actor: CompanyDomainActor = Depends(view_actor)):
    return {"success": True, "data": TenantDomainSelfService(db, actor.context, actor.admin).list()}


@router.post("", status_code=201, response_model=ApiEnvelope[DomainCreateOut])
def create_domain(body: CompanyDomainCreate, request: Request, db: Session = Depends(get_db), actor: CompanyDomainActor = Depends(edit_actor)):
    return {"success": True, "data": TenantDomainSelfService(db, actor.context, actor.admin).create(body, request=request)}


@router.post("/{domain_id}/verify", response_model=ApiEnvelope[TenantDomainOut])
def verify_domain(domain_id: str, request: Request, db: Session = Depends(get_db), actor: CompanyDomainActor = Depends(edit_actor)):
    return {"success": True, "data": TenantDomainSelfService(db, actor.context, actor.admin).action(domain_id, "verify", request=request)}


@router.post("/{domain_id}/activate", response_model=ApiEnvelope[TenantDomainOut])
def activate_domain(domain_id: str, request: Request, db: Session = Depends(get_db), actor: CompanyDomainActor = Depends(edit_actor)):
    return {"success": True, "data": TenantDomainSelfService(db, actor.context, actor.admin).action(domain_id, "activate", request=request)}


@router.post("/{domain_id}/primary", response_model=ApiEnvelope[TenantDomainOut])
def primary_domain(domain_id: str, request: Request, db: Session = Depends(get_db), actor: CompanyDomainActor = Depends(edit_actor)):
    return {"success": True, "data": TenantDomainSelfService(db, actor.context, actor.admin).action(domain_id, "primary", request=request)}


@router.get("/{domain_id}/certificate", response_model=ApiEnvelope[CertificateSummaryOut])
def certificate(domain_id: str, db: Session = Depends(get_db), actor: CompanyDomainActor = Depends(view_actor)):
    return {"success": True, "data": TenantDomainSelfService(db, actor.context, actor.admin).certificate(domain_id)}


@router.post("/{domain_id}/certificate", status_code=202, response_model=ApiEnvelope[CertificateSummaryOut])
def request_certificate(domain_id: str, body: CertificateRequestIn, request: Request,
                        idempotency_key: UUID = Header(alias="Idempotency-Key"),
                        db: Session = Depends(get_db), actor: CompanyDomainActor = Depends(edit_actor)):
    return {"success": True, "data": TenantDomainSelfService(db, actor.context, actor.admin).request_certificate(domain_id, body, idempotency_key, request=request)}
