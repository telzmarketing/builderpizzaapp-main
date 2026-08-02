"""Server-side license and commercial-module access policy."""
from __future__ import annotations

from datetime import datetime, timezone
import json

from backend.core.exceptions import DomainError
from backend.models.platform_saas import SaaSModule, TenantLicense, TenantModule
from backend.models.tenant import Tenant


class TenantAccessDenied(DomainError):
    http_status = 403


class TenantEntitlementService:
    WRITABLE_LICENSES = frozenset({"trial", "active", "grace_period"})
    READABLE_LICENSES = frozenset({"trial", "active", "grace_period", "expired", "cancelled"})

    def __init__(self, db):
        self.db = db

    def license_for(self, tenant_id: str) -> TenantLicense | None:
        return self.db.query(TenantLicense).filter(TenantLicense.tenant_id == tenant_id).first()

    def effective_license_status(self, license_row: TenantLicense | None, now: datetime | None = None) -> str:
        if license_row is None:
            return "missing"
        now = now or datetime.now(timezone.utc)
        if license_row.status == "trial" and license_row.trial_ends_at and license_row.trial_ends_at < now:
            return "expired"
        if license_row.status in {"active", "grace_period"} and license_row.expires_at and license_row.expires_at < now:
            if license_row.grace_period_ends_at and license_row.grace_period_ends_at >= now:
                return "grace_period"
            return "expired"
        return license_row.status

    def require_tenant_access(self, tenant_id: str, *, write: bool = False) -> TenantLicense:
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.deleted_at.is_(None)).first()
        if tenant is None or tenant.status != "active":
            raise TenantAccessDenied("Empresa inativa ou indisponivel.", code="TenantInactive")
        license_row = self.license_for(tenant_id)
        status = self.effective_license_status(license_row)
        allowed = self.WRITABLE_LICENSES if write else self.READABLE_LICENSES
        if status not in allowed:
            raise TenantAccessDenied(
                f"Licenca '{status}' nao permite esta operacao.",
                code="TenantLicenseDenied",
            )
        assert license_row is not None
        return license_row

    def require_module(self, tenant_id: str, module_key: str, *, write: bool = False) -> TenantModule:
        self.require_tenant_access(tenant_id, write=write)
        now = datetime.now(timezone.utc)
        result = (
            self.db.query(TenantModule, SaaSModule)
            .join(SaaSModule, SaaSModule.id == TenantModule.module_id)
            .filter(
                TenantModule.tenant_id == tenant_id,
                TenantModule.enabled.is_(True),
                SaaSModule.key == module_key,
                SaaSModule.active.is_(True),
            )
            .first()
        )
        if result is None:
            raise TenantAccessDenied(
                f"Modulo '{module_key}' nao contratado ou bloqueado.",
                code="TenantModuleDenied",
            )
        row, module = result
        if getattr(row, "starts_at", None) is not None and row.starts_at > now:
            raise TenantAccessDenied(
                f"Modulo '{module_key}' ainda nao iniciou.",
                code="TenantModuleDenied",
            )
        if getattr(row, "ends_at", None) is not None and row.ends_at <= now:
            raise TenantAccessDenied(
                f"Modulo '{module_key}' expirado.",
                code="TenantModuleDenied",
            )
        dependencies = json.loads(module.dependencies_json or "[]")
        for dependency_key in dependencies:
            dependency = (
                self.db.query(TenantModule)
                .join(SaaSModule, SaaSModule.id == TenantModule.module_id)
                .filter(
                    TenantModule.tenant_id == tenant_id,
                    TenantModule.enabled.is_(True),
                    SaaSModule.key == dependency_key,
                    SaaSModule.active.is_(True),
                )
                .first()
            )
            if dependency is None:
                raise TenantAccessDenied(
                    f"Dependencia '{dependency_key}' do modulo '{module_key}' nao esta habilitada.",
                    code="TenantModuleDependencyDenied",
                )
            if (
                getattr(dependency, "starts_at", None) is not None
                and dependency.starts_at > now
            ):
                raise TenantAccessDenied(
                    f"Dependencia '{dependency_key}' do modulo '{module_key}' ainda nao iniciou.",
                    code="TenantModuleDependencyDenied",
                )
            if (
                getattr(dependency, "ends_at", None) is not None
                and dependency.ends_at <= now
            ):
                raise TenantAccessDenied(
                    f"Dependencia '{dependency_key}' do modulo '{module_key}' expirou.",
                    code="TenantModuleDependencyDenied",
                )
        return row

    def require_within_limit(
        self, tenant_id: str, module_key: str, *, current_usage: int,
        increment: int = 1,
    ) -> TenantModule:
        row = self.require_module(tenant_id, module_key, write=True)
        if row.limit_value is not None and current_usage + increment > row.limit_value:
            raise TenantAccessDenied(
                f"Limite contratado do modulo '{module_key}' excedido.",
                code="TenantModuleLimitExceeded",
            )
        return row
