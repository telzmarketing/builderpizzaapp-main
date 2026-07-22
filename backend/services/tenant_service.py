"""Tenant and membership authorization services (not yet route-wired)."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.core.tenant_context import TenantContext, TenantContextMissing, TenantSource
from backend.models.membership import TenantMembership
from backend.models.tenant import Tenant

ACTIVE_TENANT_STATUS = "active"
ACTIVE_MEMBERSHIP_STATUS = "active"


def normalize_tenant_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").strip().lower())
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    if not slug:
        raise ValueError("Slug do tenant nao pode ser vazio.")
    return slug


class TenantService:
    def __init__(self, db: Session):
        self._db = db

    def get_active(self, tenant_id: str) -> Tenant | None:
        if not tenant_id:
            return None
        return self._db.query(Tenant).filter(
            Tenant.id == tenant_id,
            Tenant.status == ACTIVE_TENANT_STATUS,
            Tenant.deleted_at.is_(None),
        ).first()

    def require_active(self, tenant_id: str) -> Tenant:
        tenant = self.get_active(tenant_id)
        if tenant is None:
            raise TenantContextMissing("Tenant inexistente ou inativo.")
        return tenant

    def get_active_membership(self, *, user_id: str, tenant_id: str) -> TenantMembership | None:
        if not user_id or not tenant_id:
            return None
        return self._db.query(TenantMembership).filter(
            TenantMembership.user_id == user_id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == ACTIVE_MEMBERSHIP_STATUS,
        ).first()

    def panel_context(self, *, user_id: str, requested_tenant_id: str, correlation_id: str | None = None) -> TenantContext:
        """Authorize a requested selection through an active membership."""
        self.require_active(requested_tenant_id)
        membership = self.get_active_membership(user_id=user_id, tenant_id=requested_tenant_id)
        if membership is None:
            raise TenantContextMissing("Usuario nao possui membership ativo neste tenant.")
        return TenantContext(
            tenant_id=membership.tenant_id,
            source=TenantSource.PANEL,
            actor_id=user_id,
            membership_id=membership.id,
            correlation_id=correlation_id,
        )

    def soft_delete(self, tenant: Tenant) -> Tenant:
        tenant.status = "disabled"
        tenant.deleted_at = datetime.now(timezone.utc)
        tenant.updated_at = tenant.deleted_at
        return tenant
