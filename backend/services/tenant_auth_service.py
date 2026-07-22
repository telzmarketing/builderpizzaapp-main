"""Opt-in bridge between admin authentication and tenant memberships."""
from __future__ import annotations
from dataclasses import dataclass
from sqlalchemy.exc import SQLAlchemyError
from backend.models.membership import TenantMembership
from backend.models.tenant import Tenant

class TenantAuthUnavailable(RuntimeError): pass
class TenantMembershipDenied(PermissionError): pass

@dataclass(frozen=True, slots=True)
class TenantAuthSelection:
    tenant_id: str
    membership_id: str
    tenant_role: str
    tenant_name: str
    tenant_slug: str
    is_default: bool
    def claims(self):
        return {"tenant_id": self.tenant_id, "membership_id": self.membership_id, "tenant_role": self.tenant_role}

def choose_login_selection(items):
    defaults = [item for item in items if item.is_default]
    if len(defaults) == 1: return defaults[0]
    return items[0] if len(items) == 1 else None

class TenantAuthService:
    def __init__(self, db): self.db = db
    def list_active(self, user_id):
        try:
            rows = (self.db.query(TenantMembership, Tenant).join(Tenant, Tenant.id == TenantMembership.tenant_id)
                    .filter(TenantMembership.user_id == user_id, TenantMembership.status == "active",
                            Tenant.status == "active", Tenant.deleted_at.is_(None))
                    .order_by(TenantMembership.is_default.desc(), Tenant.name.asc()).all())
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise TenantAuthUnavailable("Fundacao multiempresa ainda nao esta disponivel no banco.") from exc
        return [TenantAuthSelection(m.tenant_id, m.id, m.role, t.name, t.slug, bool(m.is_default)) for m, t in rows]
    def login_selection(self, user_id): return choose_login_selection(self.list_active(user_id))
    def require_selection(self, user_id, tenant_id):
        item = next((x for x in self.list_active(user_id) if x.tenant_id == tenant_id), None)
        if item is None: raise TenantMembershipDenied("Usuario nao possui membership ativo neste tenant.")
        return item
