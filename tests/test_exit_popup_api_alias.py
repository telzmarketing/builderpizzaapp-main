"""The canonical /api path must preserve public context and admin authorization."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.core import wave6_tenant_context
from backend.core.tenant_context import TenantContext, TenantSource
from backend.database import get_db
from backend.main import app
from backend.routes import exit_popup


@pytest.fixture
def client(monkeypatch):
    context = TenantContext(
        tenant_id="store-a", source=TenantSource.PUBLIC_HOST, hostname="store.example.com"
    )
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[exit_popup.public_wave6_context] = lambda: context
    monkeypatch.setattr(wave6_tenant_context, "wave6_tenant_orm_enabled", lambda: True)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


@pytest.mark.parametrize("path", ["/exit-popup", "/api/exit-popup"])
def test_public_alias_preserves_trusted_tenant(client, monkeypatch, path):
    seen = []

    def configuration(db, tenant_id):
        seen.append(tenant_id)
        return SimpleNamespace(
            id="exit-popup-store-a", enabled=False, title="Oferta", subtitle="",
            coupon_code=None, button_text="Ver", image_url=None,
            show_once_per_session=True, trigger_delay_seconds=10, updated_at=None,
        )

    monkeypatch.setattr(exit_popup, "_get_or_create", configuration)
    response = client.get(path)
    assert response.status_code == 200
    assert response.json()["id"] == "exit-popup-store-a"
    assert seen == ["store-a"]


@pytest.mark.parametrize("path", ["/exit-popup", "/api/exit-popup"])
def test_alias_does_not_allow_anonymous_configuration_changes(client, path):
    response = client.put(path, json={})
    assert response.status_code == 401
