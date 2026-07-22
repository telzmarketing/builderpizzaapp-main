from pathlib import Path

import pytest

from backend.core.tenant_context import TenantContext, TenantContextError, TenantContextMissing, TenantSource
from backend.core.tenant_execution import (
    bind_tenant_context,
    context_from_job_metadata,
    job_metadata,
    require_bound_tenant_context,
    tenant_cache_key,
    tenant_upload_path,
)


def test_job_metadata_round_trip_uses_job_source() -> None:
    panel = TenantContext("tenant-a", TenantSource.PANEL, actor_id="u1", membership_id="m1", correlation_id="c1")
    restored = context_from_job_metadata(job_metadata(panel))
    assert restored.tenant_id == "tenant-a"
    assert restored.source == TenantSource.JOB
    assert restored.correlation_id == "c1"


def test_job_metadata_missing_tenant_fails_closed() -> None:
    with pytest.raises(TenantContextMissing):
        context_from_job_metadata({})


def test_bound_context_is_restored() -> None:
    context = TenantContext("tenant-a", TenantSource.JOB)
    with bind_tenant_context(context):
        assert require_bound_tenant_context() is context
    with pytest.raises(TenantContextMissing):
        require_bound_tenant_context()


def test_cache_key_is_tenant_namespaced() -> None:
    a = TenantContext("tenant-a", TenantSource.JOB)
    b = TenantContext("tenant-b", TenantSource.JOB)
    assert tenant_cache_key(a, "catalog", "home") != tenant_cache_key(b, "catalog", "home")


@pytest.mark.parametrize("filename", ["../secret", "folder/file.png", "..", "bad\\file"])
def test_upload_path_rejects_traversal(tmp_path: Path, filename: str) -> None:
    context = TenantContext("tenant-a", TenantSource.JOB)
    with pytest.raises(TenantContextError):
        tenant_upload_path(tmp_path, context, filename)


def test_upload_path_is_inside_tenant_directory(tmp_path: Path) -> None:
    context = TenantContext("tenant-a", TenantSource.JOB)
    assert tenant_upload_path(tmp_path, context, "asset.png") == (tmp_path / "tenant-a" / "asset.png").resolve()
