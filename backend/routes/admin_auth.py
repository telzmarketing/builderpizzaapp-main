"""
Admin authentication endpoints.

Routes
------
POST  /admin/auth/login   — email + password → JWT token
GET   /admin/auth/me      — validate token → return admin profile
POST  /admin/auth/logout  — client-side only (no server state); documented for completeness

Token flow
----------
1. Frontend POSTs credentials to /admin/auth/login.
2. Backend verifies bcrypt hash, returns { access_token, token_type, admin }.
3. Frontend stores the token (localStorage / memory) and sends it in every
   subsequent request as:  Authorization: Bearer <token>
4. Protected routes call get_current_admin() which validates the JWT.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from jose import JWTError
from sqlalchemy.orm import Session

from backend.core.response import ok, err_msg
from backend.core.security import verify_password, create_access_token, decode_access_token
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.schemas.admin import AdminLoginIn, AdminOut, TokenOut
from backend.schemas.tenant import TenantSelectionIn

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


# ── Dependency: resolve current admin from Bearer token ──────────────────────

def get_current_admin(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AdminUser:
    """
    FastAPI dependency — extracts and validates the JWT in the Authorization header.
    Use as:   admin: AdminUser = Depends(get_current_admin)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized("Token de autenticação não fornecido.")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
        admin_id: str = payload.get("sub", "")
    except JWTError:
        raise _unauthorized("Token inválido ou expirado.")

    admin = db.query(AdminUser).filter(
        AdminUser.id == admin_id,
        AdminUser.active == True,  # noqa: E712
    ).first()

    if not admin:
        raise _unauthorized("Usuário administrador não encontrado ou inativo.")

    return admin


def _unauthorized(message: str):
    """Return a 401 JSONResponse wrapped in an HTTPException-like object."""
    from fastapi import HTTPException
    return HTTPException(status_code=401, detail=message)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=None)
def admin_login(body: AdminLoginIn, db: Session = Depends(get_db)):
    """
    Authenticate an admin user and return a JWT access token.

    Request body:
        { "email": "adm@brasell.com.br", "password": "Theodonna@7" }

    Success response:
        {
          "success": true,
          "data": {
            "access_token": "<jwt>",
            "token_type": "bearer",
            "admin": { "id": "...", "email": "...", "name": "...", ... }
          },
          "message": "Bem-vindo, Administrador!"
        }
    """
    admin = db.query(AdminUser).filter(
        AdminUser.email == body.email.lower().strip(),
        AdminUser.active == True,  # noqa: E712
    ).first()

    if not admin or not verify_password(body.password, admin.password_hash):
        return err_msg(
            "E-mail ou senha inválidos.",
            code="InvalidCredentials",
            status_code=401,
        )

    # Track last login
    from datetime import datetime, timezone
    admin.last_login_at = datetime.now(timezone.utc)
    db.commit()

    extra_claims = {"email": admin.email, "name": admin.name, "role_id": admin.role_id}
    from backend.config import get_settings
    if get_settings().MULTI_TENANT_AUTH_ENABLED:
        from backend.services.tenant_auth_service import TenantAuthService, TenantAuthUnavailable
        try:
            selection = TenantAuthService(db).login_selection(admin.id)
        except TenantAuthUnavailable as exc:
            # Once tenant auth is explicitly enabled, issuing a legacy/global
            # token because the membership store is unavailable would turn an
            # operational failure into an authorization bypass.
            raise HTTPException(
                status_code=503,
                detail="Autenticacao multiempresa temporariamente indisponivel.",
            ) from exc
        if selection:
            extra_claims.update(selection.claims())
    token = create_access_token(
        subject=admin.id,
        extra=extra_claims,
    )

    result = TokenOut(
        access_token=token,
        token_type="bearer",
        admin=AdminOut.model_validate(admin),
    )
    return ok(result, f"Bem-vindo, {admin.name}!")


@router.get("/me", response_model=None)
def admin_me(current_admin: AdminUser = Depends(get_current_admin)):
    """
    Return the profile of the currently authenticated admin.

    Requires:  Authorization: Bearer <token>
    """
    return ok(AdminOut.model_validate(current_admin))


def _require_tenant_auth_enabled() -> None:
    from backend.config import get_settings
    if not get_settings().MULTI_TENANT_AUTH_ENABLED:
        raise HTTPException(status_code=404, detail="Recurso nao encontrado.")


@router.get("/tenants", response_model=None)
def admin_tenants(current_admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    from backend.services.tenant_auth_service import TenantAuthService, TenantAuthUnavailable
    _require_tenant_auth_enabled()
    try:
        items = TenantAuthService(db).list_active(current_admin.id)
    except TenantAuthUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ok([{"tenant_id": x.tenant_id, "membership_id": x.membership_id, "name": x.tenant_name,
                "slug": x.tenant_slug, "role": x.tenant_role, "is_default": x.is_default} for x in items])


@router.post("/select-tenant", response_model=None)
def select_admin_tenant(body: TenantSelectionIn, current_admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    from backend.services.tenant_auth_service import TenantAuthService, TenantAuthUnavailable, TenantMembershipDenied
    _require_tenant_auth_enabled()
    try:
        item = TenantAuthService(db).require_selection(current_admin.id, body.tenant_id)
    except TenantAuthUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TenantMembershipDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    token = create_access_token(subject=current_admin.id, extra={"email": current_admin.email,
        "name": current_admin.name, "role_id": current_admin.role_id, **item.claims()})
    return ok({"access_token": token, "token_type": "bearer"})


@router.post("/logout", response_model=None)
def admin_logout():
    """
    Logout endpoint (stateless — just instructs the client to discard the token).

    JWT tokens are not stored server-side, so revocation requires either:
      - a short expiry window (current default: JWT_EXPIRE_MINUTES)
      - or a token blacklist (Redis / DB) — add if needed.
    """
    return ok(None, "Logout realizado com sucesso.")


@router.put("/change-password", response_model=None)
def change_password(
    body: "ChangePasswordIn",
    current_admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Change the password of the currently authenticated admin.

    Request body:
        { "current_password": "...", "new_password": "..." }
    """
    if not verify_password(body.current_password, current_admin.password_hash):
        return err_msg("Senha atual incorreta.", code="WrongPassword", status_code=400)

    from backend.core.security import hash_password
    current_admin.password_hash = hash_password(body.new_password)
    db.commit()
    return ok(None, "Senha alterada com sucesso.")


# ── Inline schema for change-password ────────────────────────────────────────

from pydantic import BaseModel, Field  # noqa: E402


class ChangePasswordIn(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)
