"""Signed, tenant-scoped customer sessions."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from jose import JWTError
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.security import create_access_token, decode_access_token
from backend.models.customer import Customer


def _unauthorized(message: str = "Sessao de cliente invalida ou expirada.") -> HTTPException:
    return HTTPException(status_code=401, detail=message)


def create_customer_access_token(customer: Customer) -> tuple[str, int]:
    tenant_id = str(getattr(customer, "tenant_id", "") or "").strip()
    if not tenant_id:
        raise ValueError("Cliente sem tenant nao pode receber sessao autenticada.")
    expires_in = int(get_settings().CUSTOMER_JWT_EXPIRE_MINUTES) * 60
    now = datetime.now(timezone.utc)
    token = create_access_token(
        str(customer.id),
        {
            "token_kind": "customer",
            "tenant_id": tenant_id,
            "auth_version": int(getattr(customer, "auth_version", 0) or 0),
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
        },
        expires_at=now + timedelta(seconds=expires_in),
    )
    return token, expires_in


def authenticate_customer_token(
    authorization: str | None,
    db: Session,
    *,
    expected_tenant_id: str | None = None,
) -> Customer:
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized("Sessao de cliente nao fornecida.")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise _unauthorized() from exc
    if payload.get("token_kind") != "customer":
        raise _unauthorized("Credencial incompativel com sessao de cliente.")
    customer_id = str(payload.get("sub") or "")
    tenant_id = str(payload.get("tenant_id") or "")
    if not customer_id or not tenant_id:
        raise _unauthorized()
    if expected_tenant_id and tenant_id != expected_tenant_id:
        raise _unauthorized("Sessao nao pertence a esta loja.")
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.tenant_id == tenant_id,
    ).first()
    if not customer:
        raise _unauthorized()
    try:
        token_version = int(payload.get("auth_version", -1))
    except (TypeError, ValueError) as exc:
        raise _unauthorized() from exc
    if token_version != int(getattr(customer, "auth_version", 0) or 0):
        raise _unauthorized("Sessao revogada. Entre novamente.")
    return customer
