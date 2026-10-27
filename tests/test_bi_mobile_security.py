"""Exercise additive BI route access and trusted tenant selection without I/O."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.tenant_context import TenantContext, TenantSource
from backend.core.wave6_tenant_context import WAVE6_SESSION_TENANT_KEY, panel_wave6_context
from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.routes import bi


def client_for(*, authenticated=False, monkeypatch=None):
    app = FastAPI()
    app.include_router(bi.router, prefix="/api")
    context = TenantContext(tenant_id="bi-tenant-a", source=TenantSource.JOB)
    db = SimpleNamespace(info={WAVE6_SESSION_TENANT_KEY: context})
    app.dependency_overrides[get_db] = lambda: db
    if authenticated:
        app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id="admin")
        app.dependency_overrides[panel_wave6_context] = lambda: context
    if monkeypatch:
        class Projection:
            def __init__(self, session, tenant_id):
                assert session is db
                assert tenant_id == "bi-tenant-a"

            def analytics(self, query):
                return {"tenant": "bi-tenant-a", "period": query.period}

            analyze = analytics

        monkeypatch.setattr(bi, "BIMobileService", Projection)
    return TestClient(app)


@pytest.mark.parametrize("method,path,kwargs", [
    ("get", "/api/bi/mobile/analytics", {}),
    ("post", "/api/bi/mobile/analyze", {"json": {}}),
])
def test_mobile_routes_require_authenticated_admin(method, path, kwargs):
    with client_for() as client:
        assert getattr(client, method)(path, **kwargs).status_code == 401


def test_analytics_uses_authenticated_tenant_and_rejects_invalid_filters(monkeypatch):
    with client_for(authenticated=True, monkeypatch=monkeypatch) as client:
        response = client.get("/api/bi/mobile/analytics?period=90d&tenant_id=attacker")
        assert response.status_code == 200
        assert response.json()["data"] == {"tenant": "bi-tenant-a", "period": "90d"}
        for query in ("period=1000d", "monthly=all", "compare=guess", "date=invalid"):
            assert client.get(f"/api/bi/mobile/analytics?{query}").status_code == 422


def test_analysis_body_cannot_select_a_different_tenant(monkeypatch):
    with client_for(authenticated=True, monkeypatch=monkeypatch) as client:
        response = client.post("/api/bi/mobile/analyze", json={"period": "7d", "tenant_id": "attacker"})
        assert response.status_code == 200
        assert response.json()["data"] == {"tenant": "bi-tenant-a", "period": "7d"}
        assert client.post("/api/bi/mobile/analyze", json={"period": "invalid"}).status_code == 422
