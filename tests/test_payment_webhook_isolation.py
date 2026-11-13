import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.models.payment_config import PaymentGatewayConfig
from backend.models.tenant import Tenant
from backend.routes import payments, webhooks


KEY = "tenant_endpoint_key_1234567890"


@pytest.fixture
def webhook_app():
    app = FastAPI()
    app.include_router(payments.router, prefix="/api")
    app.include_router(webhooks.router, prefix="/api")
    yield app


def _settings(*, enabled: bool, catalog: str = "{}"):
    return SimpleNamespace(
        TENANT_PAYMENT_WEBHOOKS_ENABLED=enabled,
        TENANT_PAYMENT_WEBHOOK_ENDPOINTS=catalog,
    )


@pytest.mark.parametrize("path", [
    "/api/payments/webhook",
    "/api/webhooks/mercadopago",
    "/api/webhooks/asaas",
])
def test_global_webhook_is_disabled_when_tenant_mode_is_enabled(webhook_app, monkeypatch, path):
    settings = lambda: _settings(enabled=True)
    monkeypatch.setattr(payments, "get_settings", settings)
    monkeypatch.setattr(webhooks, "get_settings", settings)

    response = TestClient(webhook_app).post(path, json={})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AmbiguousWebhookEndpoint"


class _Query:
    def __init__(self, value):
        self.value = value

    def filter(self, *args):
        return self

    def one_or_none(self):
        return self.value

    def limit(self, _count):
        return self

    def all(self):
        return [self.value]


class _Database:
    def __init__(self):
        self.tenant = SimpleNamespace(id="tenant-a")
        self.config = SimpleNamespace(tenant_id="tenant-a")

    def query(self, model):
        if model is Tenant:
            return _Query(self.tenant)
        if model is PaymentGatewayConfig:
            return _Query(self.config)
        raise AssertionError(f"modelo inesperado: {model}")


def test_tenant_webhook_resolves_opaque_key_and_scopes_payment_service(webhook_app, monkeypatch):
    db = _Database()
    seen = {}

    class _PaymentService:
        def __init__(self, _db, tenant_id=None):
            seen["tenant_id"] = tenant_id

        def process_webhook(self, *_args):
            return {"status": "ok"}

    catalog = json.dumps({KEY: {"tenant_id": "tenant-a", "provider": "mercado_pago"}})
    monkeypatch.setattr(webhooks, "get_settings", lambda: _settings(enabled=True, catalog=catalog))
    monkeypatch.setattr(webhooks, "PaymentService", _PaymentService)
    webhook_app.dependency_overrides[get_db] = lambda: db

    try:
        response = TestClient(webhook_app).post(
            f"/api/webhooks/mercadopago/{KEY}",
            json={"type": "payment", "action": "payment.updated", "data": {"id": "payment-1"}},
        )
    finally:
        webhook_app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok"}
    assert seen["tenant_id"] == "tenant-a"


def test_tenant_webhook_rejects_missing_catalog_before_service(webhook_app, monkeypatch):
    seen = []

    class _PaymentService:
        def __init__(self, *_args, **_kwargs):
            seen.append(True)

    monkeypatch.setattr(webhooks, "get_settings", lambda: _settings(enabled=True))
    monkeypatch.setattr(webhooks, "PaymentService", _PaymentService)

    response = TestClient(webhook_app).post(
        f"/api/webhooks/mercadopago/{KEY}",
        json={"type": "payment", "data": {"id": "payment-1"}},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PaymentWebhookTenantResolutionError"
    assert seen == []
