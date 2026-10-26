"""Fail-closed tenant context construction for marketplace jobs and webhooks."""

from __future__ import annotations

from backend.core.tenant_context import TenantContext, TenantContextError, TenantSource, trusted_process_context

from .contracts import MarketplaceTenantBinding


class MarketplaceTenantBindingError(TenantContextError):
    """Raised when persisted integration metadata does not match the event."""


def resolve_marketplace_context(
    binding: MarketplaceTenantBinding,
    *,
    source: TenantSource,
    configured_provider: str,
    configured_merchant_id: str,
    integration_active: bool,
    correlation_id: str | None = None,
) -> TenantContext:
    """Build trusted context only from server-owned integration metadata.

    The event payload is intentionally absent from this API. Database-backed
    integration lookup and signature verification belong to the adapter layer;
    this function enforces the final fail-closed binding check.
    """
    if source not in {TenantSource.WEBHOOK, TenantSource.JOB}:
        raise MarketplaceTenantBindingError("Marketplace exige contexto de webhook ou job.")
    if not integration_active:
        raise MarketplaceTenantBindingError("Integracao marketplace inativa.")
    if configured_provider.strip().lower() != binding.provider.value:
        raise MarketplaceTenantBindingError("Provider nao corresponde a integracao.")
    if configured_merchant_id.strip() != binding.external_merchant_id:
        raise MarketplaceTenantBindingError("Merchant externo nao corresponde a integracao.")
    return trusted_process_context(
        binding.tenant_id,
        source=source,
        correlation_id=correlation_id,
    )

