"""Safe, read-only projection of platform runtime settings."""
from __future__ import annotations

import hmac
import ipaddress

from backend.config import DEFAULT_JWT_SECRET_KEY, Settings, get_settings
from backend.core.tenant_context import TenantContextMissing, normalize_hostname


class PlatformSettingsService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def get_settings(self) -> dict:
        """Return an explicit allowlist; never serialize the Settings object."""
        settings = self.settings
        hostnames, invalid_hostname_count = self._normalized_hostnames(
            settings.TENANT_DOMAINS_PLATFORM_HOSTNAMES
        )
        trusted_proxy_count, invalid_proxy_count = self._proxy_counts(
            settings.TENANT_DOMAINS_TRUSTED_PROXY_IPS
        )
        jwt_secret_state = self._jwt_secret_state(settings.JWT_SECRET_KEY)

        alerts = self._alerts(
            jwt_secret_state=jwt_secret_state,
            hostnames=hostnames,
            invalid_hostname_count=invalid_hostname_count,
            trusted_proxy_count=trusted_proxy_count,
            invalid_proxy_count=invalid_proxy_count,
        )
        status = "ok"
        if any(alert["severity"] == "critical" for alert in alerts):
            status = "critical"
        elif any(alert["severity"] == "warning" for alert in alerts):
            status = "attention"

        return {
            "source": "environment",
            "read_only": True,
            "restart_required": True,
            "status": status,
            "application": {
                "app_name": settings.APP_NAME,
                "app_version": settings.APP_VERSION,
                "platform_brand_name": settings.PLATFORM_BRAND_NAME,
                "debug": bool(settings.DEBUG),
            },
            "security": {
                "jwt_secret_state": jwt_secret_state,
                "platform_rbac_enabled": bool(settings.PLATFORM_RBAC_ENABLED),
                "multi_tenant_auth_enabled": bool(settings.MULTI_TENANT_AUTH_ENABLED),
            },
            "domains": {
                "enabled": bool(settings.TENANT_DOMAINS_ENABLED),
                "trust_proxy_headers": bool(
                    settings.TENANT_DOMAINS_TRUST_PROXY_HEADERS
                ),
                "platform_hostnames": hostnames,
                "platform_hostname_count": len(hostnames),
                "invalid_platform_hostname_count": invalid_hostname_count,
                "trusted_proxy_count": trusted_proxy_count,
                "invalid_trusted_proxy_count": invalid_proxy_count,
            },
            "rollout_flags": self._rollout_flags(),
            "alerts": alerts,
        }

    def _rollout_flags(self) -> list[dict]:
        settings = self.settings
        return [
            {
                "key": "tenant_identity_catalog_enforcement",
                "label": "Isolamento de identidade e catalogo",
                "enabled": bool(
                    settings.TENANT_IDENTITY_CATALOG_ENFORCEMENT_ENABLED
                ),
                "category": "isolation",
            },
            {
                "key": "tenant_customers_orders_enforcement",
                "label": "Isolamento de clientes e pedidos",
                "enabled": bool(
                    settings.TENANT_CUSTOMERS_ORDERS_ENFORCEMENT_ENABLED
                ),
                "category": "isolation",
            },
            {
                "key": "multi_tenant_wave6_orm",
                "label": "Mapeamento ORM multiempresa da onda 6",
                "enabled": bool(settings.MULTI_TENANT_WAVE6_ORM_ENABLED),
                "category": "isolation",
            },
            {
                "key": "tenant_operations_enforcement",
                "label": "Isolamento de operacoes",
                "enabled": bool(settings.TENANT_OPERATIONS_ENFORCEMENT_ENABLED),
                "category": "isolation",
            },
            {
                "key": "tenant_payment_webhooks",
                "label": "Webhooks de pagamento por empresa",
                "enabled": bool(settings.TENANT_PAYMENT_WEBHOOKS_ENABLED),
                "category": "runtime",
            },
            {
                "key": "tenant_background_context",
                "label": "Contexto de empresa em jobs",
                "enabled": bool(settings.TENANT_BACKGROUND_CONTEXT_ENABLED),
                "category": "runtime",
            },
            {
                "key": "tenant_upload_namespace",
                "label": "Namespace de uploads por empresa",
                "enabled": bool(settings.TENANT_UPLOAD_NAMESPACE_ENABLED),
                "category": "runtime",
            },
            {
                "key": "tenant_credentials",
                "label": "Credenciais isoladas por empresa",
                "enabled": bool(settings.TENANT_CREDENTIALS_ENABLED),
                "category": "security",
            },
            {
                "key": "tenant_entitlement_enforcement",
                "label": "Bloqueio de modulos e licencas",
                "enabled": bool(settings.TENANT_ENTITLEMENT_ENFORCEMENT_ENABLED),
                "category": "access",
            },
        ]

    def _alerts(
        self,
        *,
        jwt_secret_state: str,
        hostnames: list[str],
        invalid_hostname_count: int,
        trusted_proxy_count: int,
        invalid_proxy_count: int,
    ) -> list[dict]:
        settings = self.settings
        alerts: list[dict] = []

        if jwt_secret_state == "missing":
            alerts.append({
                "key": "jwt_secret_missing",
                "severity": "critical",
                "title": "Segredo JWT ausente",
                "description": "Configure o segredo JWT no ambiente antes de autenticar usuarios.",
            })
        elif jwt_secret_state == "default":
            alerts.append({
                "key": "jwt_secret_default",
                "severity": "critical",
                "title": "Segredo JWT padrao em uso",
                "description": "Substitua o segredo padrao por um valor exclusivo no ambiente.",
            })

        if settings.DEBUG:
            alerts.append({
                "key": "debug_enabled",
                "severity": "warning",
                "title": "Modo debug ativo",
                "description": "Desative o modo debug no ambiente de producao.",
            })
        if not settings.PLATFORM_RBAC_ENABLED:
            alerts.append({
                "key": "platform_rbac_disabled",
                "severity": "critical",
                "title": "RBAC da plataforma desativado",
                "description": "A Central Master permanece fail-closed enquanto o RBAC estiver desativado.",
            })
        if invalid_hostname_count:
            alerts.append({
                "key": "invalid_platform_hostnames",
                "severity": "warning",
                "title": "Hostnames de plataforma invalidos",
                "description": f"{invalid_hostname_count} entrada(s) foram ignoradas por serem invalidas.",
            })
        if settings.TENANT_DOMAINS_ENABLED and not hostnames:
            alerts.append({
                "key": "platform_hostname_missing",
                "severity": "critical",
                "title": "Hostname da plataforma ausente",
                "description": "Configure ao menos um hostname valido antes de ativar dominios.",
            })
        if invalid_proxy_count:
            alerts.append({
                "key": "invalid_trusted_proxies",
                "severity": "warning",
                "title": "Proxies confiaveis invalidos",
                "description": f"{invalid_proxy_count} entrada(s) de proxy foram ignoradas.",
            })
        if settings.TENANT_DOMAINS_TRUST_PROXY_HEADERS and not trusted_proxy_count:
            alerts.append({
                "key": "trusted_proxy_missing",
                "severity": "critical",
                "title": "Proxy confiavel ausente",
                "description": "Cabecalhos de proxy estao habilitados sem uma rede confiavel valida.",
            })
        if not settings.TENANT_ENTITLEMENT_ENFORCEMENT_ENABLED:
            alerts.append({
                "key": "entitlement_enforcement_disabled",
                "severity": "info",
                "title": "Enforcement de modulos desativado",
                "description": "A ativacao permanece condicionada aos gates de isolamento documentados.",
            })

        severity_order = {"critical": 0, "warning": 1, "info": 2}
        return sorted(
            alerts,
            key=lambda alert: (severity_order[alert["severity"]], alert["key"]),
        )

    @staticmethod
    def _jwt_secret_state(secret: str | None) -> str:
        value = secret or ""
        if not value.strip():
            return "missing"
        if hmac.compare_digest(value, DEFAULT_JWT_SECRET_KEY):
            return "default"
        return "configured"

    @staticmethod
    def _normalized_hostnames(raw: str) -> tuple[list[str], int]:
        hostnames: set[str] = set()
        invalid_count = 0
        for item in (raw or "").split(","):
            candidate = item.strip()
            if not candidate:
                continue
            try:
                hostnames.add(normalize_hostname(candidate))
            except TenantContextMissing:
                invalid_count += 1
        return sorted(hostnames), invalid_count

    @staticmethod
    def _proxy_counts(raw: str) -> tuple[int, int]:
        networks: set[str] = set()
        invalid_count = 0
        for item in (raw or "").split(","):
            candidate = item.strip()
            if not candidate:
                continue
            try:
                networks.add(str(ipaddress.ip_network(candidate, strict=False)))
            except ValueError:
                invalid_count += 1
        return len(networks), invalid_count
