"""Tenant-domain lifecycle and fail-closed public hostname resolution."""
from __future__ import annotations
import hashlib
import hmac
import ipaddress
import secrets
import uuid
from datetime import datetime, timezone
from typing import Callable
from sqlalchemy.orm import Session
from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContextMissing, normalize_hostname
from backend.models.tenant import Tenant
from backend.models.tenant_domain import TenantDomain


class TenantDomainValidationError(DomainError):
    http_status = 422


class TenantDomainConflict(DomainError):
    http_status = 409


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
            raise TenantDomainConflict("Dominio principal da plataforma nao pode ser vinculado a tenant.")
        if kind not in {"subdomain", "custom"}:
            raise TenantDomainValidationError("Tipo de dominio invalido.")
        tenant = self._db.query(Tenant).filter(
            Tenant.id == tenant_id, Tenant.status == "active", Tenant.deleted_at.is_(None)
        ).first()
        if tenant is None:
            raise TenantContextMissing("Tenant inexistente ou inativo.")
        if self._db.query(TenantDomain).filter(TenantDomain.hostname.ilike(normalized)).first() is not None:
            raise TenantDomainConflict("Hostname ja cadastrado.")
        token = secrets.token_urlsafe(32)
        domain = TenantDomain(
            id=str(uuid.uuid4()), tenant_id=tenant_id, hostname=normalized,
            kind=kind, status="awaiting_dns",
            verification_token_hash=verification_token_hash(token),
            expected_txt_record=f"_telz-verification.{normalized}",
        )
        self._db.add(domain)
        return domain, token

    @staticmethod
    def verification_challenge(domain: TenantDomain, token: str) -> dict:
        return {
            "hostname": domain.hostname,
            "record_type": "TXT",
            "record_name": domain.expected_txt_record or f"_telz-verification.{domain.hostname}",
            "record_value": token,
        }

    def confirm_verification(self, domain: TenantDomain, observed_token: str) -> TenantDomain:
        if domain.status not in {"pending", "awaiting_dns", "verifying", "dns_error"}:
            raise TenantDomainValidationError("Somente dominio pendente pode ser verificado.")
        if not hmac.compare_digest(domain.verification_token_hash, verification_token_hash(observed_token)):
            raise TenantDomainValidationError("Prova de dominio invalida.")
        domain.status = "verified"
        domain.verified_at = datetime.now(timezone.utc)
        domain.updated_at = domain.verified_at
        return domain

    def verify_dns(
        self,
        domain: TenantDomain,
        *,
        resolver: Callable[[str], list[str]] | None = None,
    ) -> TenantDomain:
        """Resolve the TXT challenge server-side and never trust a frontend boolean."""
        domain.status = "verifying"
        domain.last_checked_at = datetime.now(timezone.utc)
        try:
            if resolver is None:
                import dns.resolver

                def resolver(record_name: str) -> list[str]:
                    return [str(item).strip('"') for item in dns.resolver.resolve(record_name, "TXT")]
            observed = resolver(domain.expected_txt_record or f"_telz-verification.{domain.hostname}")
            candidate = next(
                (
                    value.removeprefix("telz-verification=")
                    for value in observed
                    if hmac.compare_digest(
                        domain.verification_token_hash,
                        verification_token_hash(value.removeprefix("telz-verification=")),
                    )
                ),
                None,
            )
            if candidate is None:
                raise TenantDomainValidationError("Registro TXT de verificacao nao encontrado.")
            self.confirm_verification(domain, candidate)
            domain.error_message = None
        except Exception as exc:
            domain.status = "dns_error"
            domain.error_message = str(exc)[:1000]
        domain.updated_at = datetime.now(timezone.utc)
        return domain

    def activate(self, domain: TenantDomain) -> TenantDomain:
        if domain.status != "verified" or domain.verified_at is None:
            raise TenantDomainValidationError("Dominio precisa estar verificado antes da publicacao.")
        domain.status = "active"
        domain.activated_at = datetime.now(timezone.utc)
        domain.updated_at = domain.activated_at
        return domain

    def set_primary(self, domain: TenantDomain) -> TenantDomain:
        if domain.status != "active":
            raise TenantDomainValidationError("Somente dominio ativo pode ser principal.")
        self._db.query(TenantDomain).filter(
            TenantDomain.tenant_id == domain.tenant_id,
            TenantDomain.id != domain.id,
        ).update({TenantDomain.is_primary: False}, synchronize_session=False)
        domain.is_primary = True
        domain.updated_at = datetime.now(timezone.utc)
        return domain

    def suspend(self, domain: TenantDomain, reason: str | None = None) -> TenantDomain:
        domain.status = "suspended"
        domain.suspended_at = datetime.now(timezone.utc)
        domain.error_message = reason
        domain.is_primary = False
        domain.updated_at = domain.suspended_at
        return domain

    def remove(self, domain: TenantDomain, reason: str | None = None) -> TenantDomain:
        domain.status = "removed"
        domain.removed_at = datetime.now(timezone.utc)
        domain.error_message = reason
        domain.is_primary = False
        domain.updated_at = domain.removed_at
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
