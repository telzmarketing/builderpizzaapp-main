"""Tenant-owned domain administration reusing the established domain lifecycle."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from backend.config import get_settings
from backend.core.domain_ssl_runtime import ssl_runtime
from backend.core.tenant_context import TenantSource
from backend.models.tenant_domain import TenantDomain
from backend.schemas.tenant_domain import TenantDomainOut
from backend.services.platform_audit_service import PlatformAuditService
from backend.services.tenant_domain_service import TenantDomainConflict, TenantDomainService, parse_hostname_set
from backend.services.tenant_domain_ssl_service import TenantDomainSSLService


class TenantDomainSelfService:
    def __init__(self, db, context, admin):
        if (context.source != TenantSource.PANEL or context.actor_id != admin.id
                or not context.membership_id):
            raise HTTPException(status_code=403, detail="Gestao de dominios exige vinculo ativo com a empresa selecionada.")
        self.db, self.context, self.admin = db, context, admin

    @staticmethod
    def public(domain):
        return TenantDomainOut.model_validate(domain).model_dump()

    def _owned_domain(self, domain_id):
        domain = self.db.query(TenantDomain).filter(
            TenantDomain.id == domain_id, TenantDomain.tenant_id == self.context.tenant_id,
            TenantDomain.status != "removed",
        ).with_for_update().first()
        if domain is None:
            raise HTTPException(status_code=404, detail="Dominio nao encontrado nesta empresa.")
        return domain

    def list(self):
        rows = self.db.query(TenantDomain).filter(TenantDomain.tenant_id == self.context.tenant_id,
            TenantDomain.status != "removed").order_by(TenantDomain.created_at.desc()).all()
        return [self.public(row) for row in rows]

    def create(self, body, *, request=None):
        runtime = ssl_runtime(get_settings())
        reserved = frozenset(runtime.platform_hostnames) or parse_hostname_set(get_settings().TENANT_DOMAINS_PLATFORM_HOSTNAMES)
        if not reserved:
            raise HTTPException(status_code=503, detail="Os dominios reservados da plataforma ainda precisam ser configurados.")
        lifecycle = TenantDomainService(self.db)
        domain, token = lifecycle.create_pending(tenant_id=self.context.tenant_id,
            hostname=body.hostname, kind=body.kind, platform_hostnames=reserved)
        PlatformAuditService(self.db).record(action="domain_created", actor=self.admin,
            tenant_id=self.context.tenant_id, resource_type="tenant_domain", resource_id=domain.id,
            metadata={"hostname": domain.hostname, "source": "company"}, request=request)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise TenantDomainConflict("Hostname ja cadastrado.") from exc
        return {"domain": self.public(domain), "verification": lifecycle.verification_challenge(domain, token)}

    def action(self, domain_id, action, *, request=None):
        domain = self._owned_domain(domain_id)
        before = self.public(domain)
        lifecycle = TenantDomainService(self.db)
        if action == "verify":
            # Rechecking an already verified binding must not demote an active store.
            if domain.status not in ("verified", "active"):
                lifecycle.verify_dns(domain)
            audit_action = "domain_verified" if domain.status in ("verified", "active") else "domain_verification_failed"
        elif action == "activate":
            lifecycle.activate(domain)
            audit_action = "domain_activated"
        elif action == "primary":
            lifecycle.set_primary(domain)
            audit_action = "domain_primary_changed"
        else:
            raise HTTPException(status_code=422, detail="Acao de dominio invalida.")
        PlatformAuditService(self.db).record(action=audit_action, actor=self.admin,
            tenant_id=self.context.tenant_id, resource_type="tenant_domain", resource_id=domain.id,
            before=before, after=self.public(domain), request=request)
        self.db.commit()
        return self.public(domain)

    def certificate(self, domain_id):
        domain = self._owned_domain(domain_id)
        return TenantDomainSSLService(self.db).summary(domain.id)

    def request_certificate(self, domain_id, body, key, *, request=None):
        domain = self._owned_domain(domain_id)
        return TenantDomainSSLService(self.db).enqueue(domain.id, body, key, actor=self.admin, request=request)
