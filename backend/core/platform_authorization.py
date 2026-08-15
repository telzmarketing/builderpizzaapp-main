"""Explicit authorization dependencies for platform-wide operations."""
from fastapi import Depends, Header, HTTPException
from jose import JWTError
from sqlalchemy.orm import Session
from backend.config import get_settings
from backend.database import get_db
from backend.core.security import decode_access_token
from backend.models.admin import AdminUser
from backend.models.platform_rbac import PlatformPermission, PlatformRolePermission, PlatformUserRole
from backend.routes.admin_auth import get_current_admin


def _reject_support_token(authorization: str | None) -> None:
    """Keep tenant support sessions out of the global control plane."""
    if not isinstance(authorization, str) or not authorization.strip():
        return
    try:
        payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
    except JWTError as exc:
        raise HTTPException(
            status_code=401,
            detail="Token invalido ou expirado.",
        ) from exc
    if payload.get("token_kind") == "support":
        raise HTTPException(
            status_code=403,
            detail="Sessao de suporte nao pode acessar a Central Master.",
        )

def has_platform_permission(db: Session, user_id: str, permission_key: str) -> bool:
    row = (db.query(PlatformUserRole.id)
           .join(PlatformRolePermission, PlatformRolePermission.role_id == PlatformUserRole.role_id)
           .join(PlatformPermission, PlatformPermission.id == PlatformRolePermission.permission_id)
           .filter(PlatformUserRole.user_id == user_id, PlatformPermission.key == permission_key)
           .first())
    return row is not None


def has_platform_role(db: Session, user_id: str) -> bool:
    return (
        db.query(PlatformUserRole.id)
        .filter(PlatformUserRole.user_id == user_id)
        .first()
        is not None
    )


def require_platform_access():
    """Authorize an authenticated platform operator without assuming a module permission."""

    def dependency(
        current_admin: AdminUser = Depends(get_current_admin),
        db: Session = Depends(get_db),
        authorization: str | None = Header(default=None),
    ) -> AdminUser:
        if not get_settings().PLATFORM_RBAC_ENABLED:
            raise HTTPException(status_code=404, detail="Recurso nao encontrado.")
        _reject_support_token(authorization)
        if not has_platform_role(db, current_admin.id):
            raise HTTPException(status_code=403, detail="Acesso de plataforma insuficiente.")
        return current_admin

    return dependency

def require_platform_permission(permission_key: str):
    normalized = (permission_key or "").strip()
    if not normalized:
        raise ValueError("permission_key e obrigatoria")

    def dependency(
        current_admin: AdminUser = Depends(get_current_admin),
        db: Session = Depends(get_db),
        authorization: str | None = Header(default=None),
    ) -> AdminUser:
        if not get_settings().PLATFORM_RBAC_ENABLED:
            raise HTTPException(status_code=404, detail="Recurso nao encontrado.")
        # FastAPI injects a string/None here. Direct unit calls leave the Header
        # descriptor as the default, while `current_admin` still represents the
        # already-authenticated dependency. Only decode an actual header value.
        _reject_support_token(authorization)
        if not has_platform_permission(db, current_admin.id, normalized):
            raise HTTPException(status_code=403, detail="Permissao de plataforma insuficiente.")
        return current_admin
    return dependency
