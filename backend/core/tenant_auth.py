"""Membership-backed tenant dependency for routes migrated to multi-tenancy."""
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException
from jose import JWTError
from backend.config import get_settings
from backend.core.security import decode_access_token
from backend.core.tenant_context import TenantContext, TenantSource
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.platform_saas import SupportSession
from backend.routes.admin_auth import get_current_admin
from backend.services.tenant_auth_service import TenantAuthService, TenantAuthUnavailable, TenantMembershipDenied

def get_current_tenant_context(
    authorization: str | None = Header(default=None),
    requested_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    admin: AdminUser = Depends(get_current_admin), db=Depends(get_db),
) -> TenantContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de autenticacao nao fornecido.")
    try:
        payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
    except JWTError as exc:
        # Keep this dependency independently fail-closed if it is reused or
        # FastAPI dependency ordering changes in the future.
        raise HTTPException(status_code=401, detail="Token invalido ou expirado.") from exc
    tenant_id = payload.get("tenant_id")
    if payload.get("token_kind") == "support":
        if requested_tenant_id and requested_tenant_id != tenant_id:
            raise HTTPException(status_code=403, detail="Tenant solicitado diverge do suporte.")
        session = db.query(SupportSession).filter(
            SupportSession.id == payload.get("support_session_id"),
            SupportSession.tenant_id == tenant_id,
            SupportSession.actor_user_id == admin.id,
            SupportSession.status == "active",
            SupportSession.expires_at > datetime.now(timezone.utc),
        ).first()
        if session is None:
            raise HTTPException(
                status_code=401,
                detail="Sessao de suporte encerrada, revogada ou expirada.",
            )
        return TenantContext(
            tenant_id=session.tenant_id,
            source=TenantSource.SUPPORT,
            actor_id=admin.id,
            support_session_id=session.id,
        )
    if not get_settings().MULTI_TENANT_AUTH_ENABLED:
        raise HTTPException(status_code=404, detail="Recurso nao encontrado.")
    membership_id = payload.get("membership_id")
    if not tenant_id or not membership_id:
        raise HTTPException(status_code=409, detail="Selecione uma empresa para continuar.")
    if requested_tenant_id and requested_tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant solicitado diverge do token.")
    try:
        item = TenantAuthService(db).require_selection(admin.id, tenant_id)
    except TenantAuthUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TenantMembershipDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if item.membership_id != membership_id:
        raise HTTPException(status_code=403, detail="Membership do token nao esta mais ativa.")
    return TenantContext(tenant_id=item.tenant_id, source=TenantSource.PANEL,
                         actor_id=admin.id, membership_id=item.membership_id)
