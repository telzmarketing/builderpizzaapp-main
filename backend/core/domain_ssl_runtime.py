"""Read only the root-owned public projection of the domain SSL bootstrap."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import ipaddress
import json
import os
from pathlib import Path
import stat

from backend.config import get_settings
from backend.core.tenant_context import normalize_hostname


RUNTIME_PATH = Path("/var/lib/telz/domain-ssl/runtime.json")
REASONS = {
    "setup_required": "A configuracao automatica HTTPS ainda nao foi concluida nesta instalacao.",
    "disabled": "A emissao HTTPS esta desabilitada nesta instalacao.",
    "invalid_runtime": "A configuracao automatica HTTPS precisa ser revisada pelo administrador da plataforma.",
    "missing_public_ip": "A plataforma ainda nao possui IP publico autorizado para emitir certificados.",
    "missing_platform_hosts": "Os dominios reservados da plataforma ainda nao foram configurados.",
    "preflight_failed": "A verificacao de infraestrutura HTTPS ainda nao foi concluida.",
    "release_unavailable": "A instalacao ainda precisa de uma release validada para emitir certificados.",
    "worker_unavailable": "O executor HTTPS esta indisponivel. Tente novamente em instantes.",
}


@dataclass(frozen=True)
class DomainSSLRuntime:
    ready: bool
    public_ips: tuple[str, ...] = ()
    platform_hostnames: tuple[str, ...] = ()
    reason: str | None = None


def _public_ips(values):
    if not isinstance(values, list) or len(values) > 32:
        raise ValueError("Invalid public address list")
    addresses = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError("Invalid public address")
        address = ipaddress.ip_address(value)
        if not address.is_global or address.is_multicast or address.is_reserved:
            raise ValueError("Invalid public address")
        addresses.append(str(address))
    return tuple(sorted(set(addresses)))


def _hosts(values):
    if not isinstance(values, list) or len(values) > 100 or any(not isinstance(value, str) for value in values):
        raise ValueError("Invalid reserved hostname list")
    return tuple(sorted({normalize_hostname(value) for value in values}))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate projection key")
        result[key] = value
    return result


def read_runtime(path=None):
    """None means absent; invalid or mutable projections never become ready."""
    path = path if path is not None else RUNTIME_PATH
    try:
        path.lstat()
        if not path.is_absolute():
            raise ValueError("Projection path must be absolute")
        for parent in path.parents:
            info = parent.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError("Unsafe projection parent")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            visible = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or not stat.S_ISREG(visible.st_mode)
                    or info.st_uid != 0 or info.st_nlink != 1 or info.st_mode & 0o022
                    or info.st_size > 8192 or (info.st_dev, info.st_ino) != (visible.st_dev, visible.st_ino)):
                raise ValueError("Unsafe projection file")
            raw = stream.read(8193)
        if len(raw.encode("utf-8")) > 8192:
            raise ValueError("Projection too large")
        data = json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Invalid constant")))
        if (not isinstance(data, dict) or set(data) != {"schema_version", "ready", "public_ips", "platform_hostnames", "reason", "updated_at"}
                or type(data["schema_version"]) is not int or data["schema_version"] != 1
                or type(data["ready"]) is not bool or data["reason"] not in {None, *REASONS}
                or not isinstance(data["updated_at"], str)
                or datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")).tzinfo is None):
            raise ValueError("Invalid runtime projection")
        ips, hosts = _public_ips(data["public_ips"]), _hosts(data["platform_hostnames"])
        if data["ready"] and (not ips or not hosts or data["reason"] is not None):
            raise ValueError("Incomplete ready projection")
        return DomainSSLRuntime(data["ready"], ips, hosts,
                                data["reason"] or (None if data["ready"] else "preflight_failed"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, TypeError, KeyError):
        return DomainSSLRuntime(False, reason="invalid_runtime")


def ssl_runtime(settings=None):
    settings = settings or get_settings()
    mode = getattr(settings, "TENANT_DOMAIN_SSL_MODE", "auto")
    if mode == "disabled":
        return DomainSSLRuntime(False, reason="disabled")
    if mode == "auto":
        projection = read_runtime()
        if projection is not None:
            return projection
    if not settings.TENANT_DOMAIN_SSL_ENABLED:
        return DomainSSLRuntime(False, reason="setup_required" if mode == "auto" else "disabled")
    try:
        ips = _public_ips([item.strip() for item in settings.TENANT_DOMAIN_SSL_PUBLIC_IPS.split(",") if item.strip()])
        hosts = _hosts([item.strip() for item in settings.TENANT_DOMAINS_PLATFORM_HOSTNAMES.split(",") if item.strip()])
        if not ips:
            return DomainSSLRuntime(False, reason="missing_public_ip")
        if not hosts:
            return DomainSSLRuntime(False, reason="missing_platform_hosts")
        return DomainSSLRuntime(True, ips, hosts)
    except (ValueError, TypeError):
        return DomainSSLRuntime(False, reason="invalid_runtime")
