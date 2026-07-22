import pytest

from backend.core.tenant_context import (
    TenantContext,
    TenantContextError,
    TenantContextMismatch,
    TenantContextMissing,
    TenantSource,
    normalize_hostname,
    public_host_context,
    trusted_process_context,
)


def test_context_rejects_empty_tenant() -> None:
    with pytest.raises(TenantContextMissing):
        trusted_process_context(None, source=TenantSource.JOB)


def test_panel_context_requires_actor_and_membership() -> None:
    with pytest.raises(TenantContextMissing):
        TenantContext(tenant_id="tenant-a", source=TenantSource.PANEL)


def test_public_host_has_no_default_fallback() -> None:
    with pytest.raises(TenantContextMissing):
        public_host_context("unknown.example.com", resolver=lambda _host: None)


def test_public_host_uses_server_side_resolver() -> None:
    context = public_host_context("Store.Example.COM.:443", resolver=lambda host: "tenant-a" if host == "store.example.com" else None)
    assert context.tenant_id == "tenant-a"
    assert context.hostname == "store.example.com"


def test_resource_ownership_is_fail_closed() -> None:
    context = trusted_process_context("tenant-a", source=TenantSource.WEBHOOK)
    context.assert_tenant("tenant-a")
    with pytest.raises(TenantContextMismatch):
        context.assert_tenant("tenant-b")
    with pytest.raises(TenantContextMismatch):
        context.assert_tenant(None)


def test_process_context_only_accepts_non_http_sources() -> None:
    with pytest.raises(TenantContextError):
        trusted_process_context("tenant-a", source=TenantSource.PANEL)


@pytest.mark.parametrize("hostname", ["", "example.com/path", "user@example.com", "bad host", "bad_host", ".example.com", "example.com:0", "example.com:abc"])
def test_hostname_validation_rejects_unsafe_values(hostname: str) -> None:
    with pytest.raises(TenantContextMissing):
        normalize_hostname(hostname)
