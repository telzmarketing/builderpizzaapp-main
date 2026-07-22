"""Tenant-domain lifecycle and fail-closed public hostname resolution."""
from __future__ import annotations
import hashlib
import hmac
import ipaddress
import secrets
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.core.tenant_context import TenantContextMissing, normalize_hostname
from backend.models.tenant import Tenant
from backend.models.tenant_domain import TenantDomain


def parse_hostname_set(raw: str) -> frozenset[str]:
    return frozenset(normalize_hostname(item) for item in raw.split(",") if item.strip())


def remote_is_trusted(remote_addr: str | None, trusted_proxy_ips: str) -> bool:
    if not remote_addr:
        return False
    try:
        address = ipaddress.ip_address(remote_addr.strip())
    except ValueError:
        return False
    for item in trusted_proxy_ips.split(","):
        candidate = item.strip()
        if not candidate:
            continue
        try:
            if address in ipaddress.ip_network(candidate, strict=False):
                return True
        except ValueError:
            continue
    return False


def trusted_request_hostname(*, direct_host: str | None, forwarded_host: str | None,
                             remote_addr: str | None, trust_proxy_headers: bool,
                             trusted_proxy_ips: str) -> str:
    selected = direct_host
    if trust_proxy_headers and remote_is_trusted(remote_addr, trusted_proxy_ips):
        selected = (forwarded_host or "").split(",", 1)[0].strip() or direct_host
    return normalize_hostname(selected)


def verification_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TenantDomainService:
    def __init__(self, db: Session):
        self._db = db

    def create_pending(self, *, tenant_id: str, hostname: str, kind: str,
                       platform_hostnames: frozenset[str]) -> tuple[TenantDomain, str]:
        normalized = normalize_hostname(hostname)
        if normalized in platform_hostnames:
            raise ValueError("Dominio principal da plataforma nao pode ser vinculado a tenant.")
        if kind not in {"subdomain", "custom"}:
            raise ValueError("Tipo de dominio invalido.")
        tenant = self._db.query(Tenant).filter(
            Tenant.id == tenant_id, Tenant.status == "active", Tenant.deleted_at.is_(None)
        ).first()
        if tenant is None:
            raise TenantContextMissing("Tenant inexistente ou inativo.")
        if self._db.query(TenantDomain).filter(TenantDomain.hostname.ilike(normalized)).first() is not None:
            raise ValueError("Hostname ja cadastrado.")
        token = secrets.token_urlsafe(32)
        domain = TenantDomain(id=str(uuid.uuid4()), tenant_id=tenant_id, hostname=normalized,
                              kind=kind, status="pending",
                              verification_token_hash=verification_token_hash(token))
        self._db.add(domain)
        return domain, token

    def confirm_verification(self, domain: TenantDomain, observed_token: str) -> TenantDomain:
        if domain.status != "pending":
            raise ValueError("Somente dominio pendente pode ser verificado.")
        if not hmac.compare_digest(domain.verification_token_hash, verification_token_hash(observed_token)):
            raise ValueError("Prova de dominio invalida.")
        domain.status = "verified"
        domain.verified_at = datetime.now(timezone.utc)
        domain.updated_at = domain.verified_at
        return domain

    def activate(self, domain: TenantDomain) -> TenantDomain:
        if domain.status != "verified" or domain.verified_at is None:
            raise ValueError("Dominio precisa estar verificado antes da publicacao.")
        domain.status = "active"
        domain.activated_at = datetime.now(timezone.utc)
        domain.updated_at = domain.activated_at
        return domain

    def resolve_active_tenant_id(self, hostname: str, *, platform_hostnames: frozenset[str]) -> str | None:
        normalized = normalize_hostname(hostname)
        if normalized in platform_hostnames:
            return None
        row = self._db.query(TenantDomain.tenant_id).join(Tenant, Tenant.id == TenantDomain.tenant_id).filter(
            TenantDomain.hostname.ilike(normalized), TenantDomain.status == "active",
            Tenant.status == "active", Tenant.deleted_at.is_(None),
        ).first()
        return row[0] if row else None
