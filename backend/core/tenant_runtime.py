"""Trusted tenant resolution for incrementally migrated HTTP routes."""
from __future__ import annotations

from fastapi import HTTPException, Request
from jose import JWTError
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.security import decode_access_token
from backend.core.tenant_auth import get_current_tenant_context
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.admin import AdminUser
from backend.services.tenant_domain_service import (
    TenantDomainService,
    parse_hostname_set,
    trusted_request_hostname,
)


def resolve_panel_tenant_context(
    request: Request, db: Session, admin: AdminUser
) -> TenantContext | None:
    """Resolve a membership-backed context only when panel tenancy is enabled."""
    if not get_settings().MULTI_TENANT_AUTH_ENABLED:
        return None
    authorization = request.headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        try:
            payload = decode_access_token(
                authorization.removeprefix("Bearer ").strip()
            )
        except JWTError:
            payload = {}
        if payload.get("token_kind") == "support":
            return get_current_tenant_context(
                authorization=authorization,
                requested_tenant_id=request.headers.get("x-tenant-id"),
                admin=admin,
                db=db,
            )
    return get_current_tenant_context(
        authorization=authorization,
        requested_tenant_id=request.headers.get("x-tenant-id"),
        admin=admin,
        db=db,
    )


def resolve_public_tenant_context(request: Request, db: Session) -> TenantContext | None:
    """Resolve an active tenant from a trusted request hostname, fail closed."""
    settings = get_settings()
    if not settings.TENANT_DOMAINS_ENABLED:
        return None
    hostname = trusted_request_hostname(
        direct_host=request.headers.get("host"),
        forwarded_host=request.headers.get("x-forwarded-host"),
        remote_addr=request.client.host if request.client else None,
        trust_proxy_headers=settings.TENANT_DOMAINS_TRUST_PROXY_HEADERS,
        trusted_proxy_ips=settings.TENANT_DOMAINS_TRUSTED_PROXY_IPS,
    )
    tenant_id = TenantDomainService(db).resolve_active_tenant_id(
        hostname,
        platform_hostnames=parse_hostname_set(settings.TENANT_DOMAINS_PLATFORM_HOSTNAMES),
    )
    if not tenant_id:
        raise HTTPException(status_code=404, detail="Loja nao encontrada para este dominio.")
    return TenantContext(tenant_id=tenant_id, source=TenantSource.PUBLIC_HOST, hostname=hostname)
