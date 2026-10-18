"""Host-bound branding in the existing namespaced configuration store."""
import json
from dataclasses import dataclass
from fastapi import Request
from sqlalchemy import text
from backend.config import get_settings
from backend.core.exceptions import DomainError
from backend.core.tenant_auth import get_current_tenant_context
from backend.core.tenant_context import TenantContextMissing
from backend.models.tenant import Tenant
from backend.services.tenant_domain_service import TenantDomainService, parse_hostname_set, trusted_request_hostname


class SiteConfigNotFound(DomainError):
    http_status = 404


class SiteConfigForbidden(DomainError):
    http_status = 403


@dataclass(frozen=True)
class SiteIdentity:
    platform: bool = False
    tenant_id: str | None = None
    legacy: bool = False


class SiteConfigService:
    def __init__(self, db):
        self.db = db

    def identity(self, request: Request) -> SiteIdentity:
        settings = get_settings()
        tenancy = settings.TENANT_DOMAINS_ENABLED or settings.MULTI_TENANT_AUTH_ENABLED
        try:
            hostname = trusted_request_hostname(
                direct_host=request.headers.get("host"), forwarded_host=request.headers.get("x-forwarded-host"),
                remote_addr=request.client.host if request.client else None,
                trust_proxy_headers=settings.TENANT_DOMAINS_TRUST_PROXY_HEADERS,
                trusted_proxy_ips=settings.TENANT_DOMAINS_TRUSTED_PROXY_IPS,
            )
        except TenantContextMissing as exc:
            if not tenancy:
                return SiteIdentity(legacy=True)
            raise SiteConfigNotFound("Loja nao encontrada para este dominio.") from exc
        platform_hosts = parse_hostname_set(settings.TENANT_DOMAINS_PLATFORM_HOSTNAMES) | {"app.telz.com.br"}
        if hostname in platform_hosts:
            return SiteIdentity(platform=True)
        if not tenancy:
            return SiteIdentity(legacy=True)
        tenant_id = TenantDomainService(self.db).resolve_active_tenant_id(hostname, platform_hostnames=frozenset(platform_hosts))
        if not tenant_id:
            raise SiteConfigNotFound("Loja nao encontrada para este dominio.")
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        return SiteIdentity(tenant_id=tenant_id, legacy=bool(tenant and tenant.is_legacy))

    @staticmethod
    def key(tenant_id):
        return f"tenant:{tenant_id}:site-content" if tenant_id else "default"

    def _read(self, key):
        row = self.db.execute(text("SELECT content, updated_at FROM site_config WHERE id = :key"), {"key": key}).fetchone()
        if row is None:
            return None
        try:
            content = json.loads(row[0]) if row[0] else {}
        except (ValueError, TypeError):
            content = {}
        return (content if isinstance(content, dict) else {}), row[1]

    def read(self, request):
        identity = self.identity(request)
        if identity.platform:
            return {"brand": {"name": "Telz", "pageTitle": "Telz", "faviconUrl": "/icons/telz.svg"}}, None, identity
        stored = self._read(self.key(identity.tenant_id))
        if stored is None and identity.tenant_id and identity.legacy:
            stored = self._read("default")
        content, updated_at = stored or ({}, None)
        return content, updated_at, identity

    def save(self, request, admin, content):
        identity = self.identity(request)
        tenant_id = identity.tenant_id
        if identity.platform or tenant_id or get_settings().MULTI_TENANT_AUTH_ENABLED:
            context = get_current_tenant_context(
                authorization=request.headers.get("authorization"), requested_tenant_id=request.headers.get("x-tenant-id"),
                admin=admin, db=self.db,
            )
            if tenant_id and context.tenant_id != tenant_id:
                raise SiteConfigForbidden("Empresa selecionada diverge do dominio.")
            tenant_id = context.tenant_id
        self.db.execute(text(
            "INSERT INTO site_config (id, content, updated_at) VALUES (:key, :content, CURRENT_TIMESTAMP) "
            "ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, updated_at = CURRENT_TIMESTAMP"
        ), {"key": self.key(tenant_id), "content": json.dumps(content, ensure_ascii=False)})
        self.db.commit()
        return content

    @staticmethod
    def favicon(content, size, identity):
        if identity.platform:
            return "/icons/telz.svg"
        brand = content.get("brand")
        raw = str(brand.get("faviconUrl") or "").strip().replace("\\", "/") if isinstance(brand, dict) else ""
        extensions = (".apng", ".avif", ".gif", ".ico", ".jpeg", ".jpg", ".jfif", ".pjpeg", ".pjp", ".png", ".svg", ".webp")
        if raw and not raw.startswith("data:") and raw.lower().endswith(extensions):
            if raw.startswith(("http://", "https://", "/")):
                return raw
            return f"/{raw}" if raw.startswith(("uploads/", "api/uploads/")) else f"/uploads/{raw}"
        if identity.legacy:
            return "/icons/favicon-moschettieri-32.png" if size <= 64 else "/icons/icon-512.png" if size >= 512 else "/icons/icon-192.png"
        return "/icons/store-default.svg"

    @staticmethod
    def version(updated_at):
        if isinstance(updated_at, str):
            from datetime import datetime
            updated_at = datetime.fromisoformat(updated_at)
        return str(int(updated_at.timestamp())) if updated_at else "default"

    def favicon_target(self, request, size):
        content, updated_at, identity = self.read(request)
        target = self.favicon(content, size, identity)
        if target.startswith("/"):
            separator = "&" if "?" in target else "?"
            target = f"{target}{separator}v={self.version(updated_at)}"
        return target

    def manifest(self, request):
        content, updated_at, identity = self.read(request)
        brand = content.get("brand")
        brand = brand if isinstance(brand, dict) else {}
        name = str(brand.get("pageTitle") or brand.get("name") or "Sua Loja").strip()
        short_name = str(brand.get("name") or "Sua Loja").strip()
        version = self.version(updated_at)
        return {
            "name": name, "short_name": short_name[:24] or "Sua Loja",
            "description": "Gestor Telz" if identity.platform else "Loja online",
            "start_url": "/painel" if identity.platform else "/motoboy",
            "scope": "/painel" if identity.platform else "/motoboy",
            "display": "standalone", "display_override": ["fullscreen", "standalone"],
            "orientation": "portrait", "theme_color": "#000000", "background_color": "#000000",
            "icons": [{"src": f"/api/site-config/favicon?size={size}&v={version}",
                       "sizes": f"{size}x{size}", "purpose": "any maskable"} for size in (192, 512)],
        }
