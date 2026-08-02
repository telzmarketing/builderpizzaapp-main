"""Trusted tenant context primitives.

This module is intentionally not wired into existing routes yet.  Callers must
resolve a tenant through a trusted server-side source before constructing the
context; an arbitrary ``tenant_id`` from a request is never sufficient.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import ipaddress
import re
from typing import Protocol


class TenantContextError(ValueError):
    """Base error for fail-closed tenant resolution."""


class TenantContextMissing(TenantContextError):
    """Raised when no trusted tenant can be established."""


class TenantContextMismatch(TenantContextError):
    """Raised when untrusted input conflicts with the trusted tenant."""


class TenantSource(str, Enum):
    PANEL = "panel"
    SUPPORT = "support"
    PUBLIC_HOST = "public_host"
    WEBHOOK = "webhook"
    JOB = "job"


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: str
    source: TenantSource
    actor_id: str | None = None
    membership_id: str | None = None
    support_session_id: str | None = None
    hostname: str | None = None
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, TenantSource):
            raise TenantContextError("Fonte de tenant invalida.")
        tenant_id = self.tenant_id.strip() if self.tenant_id else ""
        if not tenant_id:
            raise TenantContextMissing("Tenant confiavel nao resolvido.")
        object.__setattr__(self, "tenant_id", tenant_id)
        if self.source == TenantSource.PANEL and (not self.actor_id or not self.membership_id):
            raise TenantContextMissing("Contexto do painel exige ator e membership validos.")
        if self.source == TenantSource.SUPPORT and (
            not self.actor_id or not self.support_session_id
        ):
            raise TenantContextMissing("Contexto de suporte exige ator e sessao validos.")
        if self.source == TenantSource.PUBLIC_HOST and not self.hostname:
            raise TenantContextMissing("Contexto publico exige hostname validado.")

    def assert_tenant(self, resource_tenant_id: str | None) -> None:
        if not resource_tenant_id or resource_tenant_id != self.tenant_id:
            raise TenantContextMismatch("Recurso nao pertence ao tenant do contexto.")


class PublicHostTenantResolver(Protocol):
    def __call__(self, hostname: str) -> str | None: ...


def normalize_hostname(hostname: str | None) -> str:
    """Normalize a hostname without trusting forwarded headers or resolving DNS."""
    value = (hostname or "").strip().lower().rstrip(".")
    if any(char.isspace() for char in value):
        raise TenantContextMissing("Hostname publico invalido.")
    if not value or "/" in value or "\\" in value or "@" in value:
        raise TenantContextMissing("Hostname publico invalido.")
    # Request.url.hostname normally removes the port; support direct utility use.
    if value.startswith("["):
        end = value.find("]")
        if end < 0 or value[end + 1 :] not in {"",} and not value[end + 1 :].startswith(":"):
            raise TenantContextMissing("Hostname publico invalido.")
        value = value[1:end]
    elif value.count(":") == 1:
        host, port = value.rsplit(":", 1)
        if not port.isdigit() or int(port) not in range(1, 65536):
            raise TenantContextMissing("Porta do hostname invalida.")
        value = host.rstrip(".")
    elif ":" in value:
        raise TenantContextMissing("Hostname publico invalido.")
    if len(value) not in range(1, 254) or not re.fullmatch(r"[a-z0-9.-]+", value):
        raise TenantContextMissing("Hostname publico invalido.")
    labels = value.split(".")
    if any(not label or len(label) not in range(1, 64) or label.startswith("-") or label.endswith("-") for label in labels):
        raise TenantContextMissing("Hostname publico invalido.")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        raise TenantContextMissing("Endereco IP nao pode ser usado como hostname publico.")
    return value


def public_host_context(
    hostname: str | None,
    *,
    resolver: PublicHostTenantResolver,
    correlation_id: str | None = None,
) -> TenantContext:
    normalized = normalize_hostname(hostname)
    tenant_id = resolver(normalized)
    if not tenant_id:
        # Deliberately no legacy/default fallback.
        raise TenantContextMissing("Hostname nao esta associado a tenant ativo.")
    return TenantContext(
        tenant_id=tenant_id,
        source=TenantSource.PUBLIC_HOST,
        hostname=normalized,
        correlation_id=correlation_id,
    )


def trusted_process_context(
    tenant_id: str | None,
    *,
    source: TenantSource,
    correlation_id: str | None = None,
) -> TenantContext:
    """Build context from persisted webhook/job metadata, never request input."""
    if source not in {TenantSource.WEBHOOK, TenantSource.JOB}:
        raise TenantContextError("Fonte permitida apenas para webhook ou job.")
    return TenantContext(tenant_id=tenant_id or "", source=source, correlation_id=correlation_id)
