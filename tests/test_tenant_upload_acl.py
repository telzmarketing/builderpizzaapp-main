from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend.core.tenant_context import TenantContext, TenantSource
from backend.services import tenant_upload_service as module
from backend.services.tenant_upload_service import TenantUploadService


def _request(headers: dict[str, str] | None = None) -> Request:
    normalized = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    return Request({"type": "http", "method": "GET", "path": "/uploads/tenant-a/asset.png", "headers": normalized})


def _service_with(asset):
    service = TenantUploadService(SimpleNamespace())
    service.asset_for_storage_key = lambda key: asset
    return service


def test_public_upload_rejects_a_different_public_tenant(monkeypatch):
    asset = SimpleNamespace(tenant_id="tenant-a", visibility="public")
    monkeypatch.setattr(module, "resolve_public_tenant_context", lambda *_: TenantContext("tenant-b", TenantSource.PUBLIC_HOST, hostname="b.example.test"))

    with pytest.raises(HTTPException) as exc:
        _service_with(asset).require_read_access(_request(), "tenant-a/asset.png")
    assert exc.value.status_code == 404


def test_public_upload_allows_its_trusted_hostname(monkeypatch):
    asset = SimpleNamespace(tenant_id="tenant-a", visibility="public")
    monkeypatch.setattr(module, "resolve_public_tenant_context", lambda *_: TenantContext("tenant-a", TenantSource.PUBLIC_HOST, hostname="a.example.test"))

    assert _service_with(asset).require_read_access(_request(), "tenant-a/asset.png") is asset


def test_private_upload_requires_panel_context_of_same_tenant(monkeypatch):
    asset = SimpleNamespace(tenant_id="tenant-a", visibility="private")
    monkeypatch.setattr(module, "authenticate_admin_token", lambda *_: SimpleNamespace(id="admin-a"))
    monkeypatch.setattr(module, "resolve_panel_tenant_context", lambda *_: TenantContext("tenant-b", TenantSource.PANEL, actor_id="admin-a", membership_id="membership-b"))

    with pytest.raises(HTTPException) as exc:
        _service_with(asset).require_read_access(_request({"authorization": "Bearer token"}), "tenant-a/secret.mp3")
    assert exc.value.status_code == 404


def test_private_upload_allows_panel_context_of_same_tenant(monkeypatch):
    asset = SimpleNamespace(tenant_id="tenant-a", visibility="private")
    monkeypatch.setattr(module, "authenticate_admin_token", lambda *_: SimpleNamespace(id="admin-a"))
    monkeypatch.setattr(module, "resolve_panel_tenant_context", lambda *_: TenantContext("tenant-a", TenantSource.PANEL, actor_id="admin-a", membership_id="membership-a"))

    assert _service_with(asset).require_read_access(_request({"authorization": "Bearer token"}), "tenant-a/secret.mp3") is asset


def test_unknown_or_legacy_upload_has_no_implicit_tenant_assignment():
    with pytest.raises(HTTPException) as exc:
        _service_with(None).require_read_access(_request(), "legacy-file.png")
    assert exc.value.status_code == 404
