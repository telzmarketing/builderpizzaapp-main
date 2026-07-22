"""Tenant-safe primitives for jobs, cache keys and local files."""
from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar, Token
import re
from pathlib import Path
from typing import Iterator, Mapping
from backend.core.tenant_context import TenantContext, TenantContextError, TenantContextMissing, TenantSource, trusted_process_context

_current_context: ContextVar[TenantContext | None] = ContextVar("tenant_context", default=None)
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

def job_metadata(context: TenantContext) -> dict[str, str]:
    if context.source not in {TenantSource.PANEL, TenantSource.WEBHOOK, TenantSource.JOB}:
        raise TenantContextError("Fonte nao autorizada para enfileirar job.")
    result = {"tenant_id": context.tenant_id}
    if context.correlation_id:
        result["correlation_id"] = context.correlation_id
    return result

def context_from_job_metadata(metadata: Mapping[str, object]) -> TenantContext:
    tenant_id, correlation_id = metadata.get("tenant_id"), metadata.get("correlation_id")
    return trusted_process_context(tenant_id if isinstance(tenant_id, str) else None, source=TenantSource.JOB, correlation_id=correlation_id if isinstance(correlation_id, str) else None)

@contextmanager
def bind_tenant_context(context: TenantContext) -> Iterator[TenantContext]:
    token: Token[TenantContext | None] = _current_context.set(context)
    try:
        yield context
    finally:
        _current_context.reset(token)

def require_bound_tenant_context() -> TenantContext:
    context = _current_context.get()
    if context is None:
        raise TenantContextMissing("Execucao sem TenantContext confiavel.")
    return context

def tenant_cache_key(context: TenantContext, namespace: str, key: str) -> str:
    for value in (namespace, key):
        if not value or any(char in value for char in "\r\n\x00"):
            raise TenantContextError("Chave de cache invalida.")
    return f"tenant:{context.tenant_id}:{namespace}:{key}"

def tenant_upload_path(root: Path, context: TenantContext, filename: str) -> Path:
    if not _SAFE_SEGMENT.fullmatch(context.tenant_id):
        raise TenantContextError("Identificador de tenant inseguro para filesystem.")
    if not _SAFE_SEGMENT.fullmatch(filename) or filename in {".", ".."}:
        raise TenantContextError("Nome de arquivo inseguro.")
    resolved_root = root.resolve()
    tenant_root = (resolved_root / context.tenant_id).resolve()
    destination = (tenant_root / filename).resolve()
    if destination.parent != tenant_root or resolved_root not in destination.parents:
        raise TenantContextError("Caminho de upload fora do namespace permitido.")
    return destination
