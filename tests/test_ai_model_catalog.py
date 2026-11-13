from types import SimpleNamespace

import httpx
import pytest

from backend.services.ai.model_catalog import AIModelCatalogError, list_provider_models
from backend.routes.ai_credentials import list_central_models


def test_openai_catalog_is_normalized_and_sorted(monkeypatch):
    captured = {}

    def fake_get(url, *, headers, timeout):
        captured.update(url=url, headers=headers, timeout=timeout)
        return httpx.Response(200, json={"data": [
            {"id": "gpt-4o", "owned_by": "openai", "created": 2},
            {"id": "gpt-4o-mini", "owned_by": "openai", "created": 1},
        ]})

    monkeypatch.setattr("backend.services.ai.model_catalog.httpx.get", fake_get)
    result = list_provider_models(SimpleNamespace(provider="openai", api_key="sk-secret"))

    assert [item["id"] for item in result] == ["gpt-4o", "gpt-4o-mini"]
    assert captured["url"] == "https://api.openai.com/v1/models"
    assert captured["headers"] == {"Authorization": "Bearer sk-secret"}


def test_claude_catalog_uses_anthropic_headers(monkeypatch):
    captured = {}

    def fake_get(url, *, headers, timeout):
        captured.update(url=url, headers=headers)
        return httpx.Response(200, json={"data": [{"id": "claude-sonnet-4-20250514", "display_name": "Claude Sonnet"}]})

    monkeypatch.setattr("backend.services.ai.model_catalog.httpx.get", fake_get)
    result = list_provider_models(SimpleNamespace(provider="claude", api_key="anthropic-secret"))

    assert result[0]["name"] == "Claude Sonnet"
    assert captured["url"] == "https://api.anthropic.com/v1/models"
    assert captured["headers"]["x-api-key"] == "anthropic-secret"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"


def test_provider_error_never_contains_the_api_key(monkeypatch):
    secret = "sk-super-secret"

    def fake_get(*args, **kwargs):
        raise httpx.ConnectError("provider unavailable")

    monkeypatch.setattr("backend.services.ai.model_catalog.httpx.get", fake_get)
    with pytest.raises(AIModelCatalogError) as exc_info:
        list_provider_models(SimpleNamespace(provider="openai", api_key=secret))

    assert secret not in str(exc_info.value)


class _Query:
    def __init__(self, value):
        self.value = value

    def filter(self, *_args):
        return self

    def first(self):
        return self.value


class _DB:
    def __init__(self, value):
        self.value = value

    def query(self, _model):
        return _Query(self.value)


def test_endpoint_uses_the_authenticated_tenant_credential_and_never_returns_key(monkeypatch):
    credential = SimpleNamespace(provider="openai", api_key="sk-tenant-secret")
    actor = SimpleNamespace(tenant_id="tenant-a")
    monkeypatch.setattr(
        "backend.routes.ai_credentials.list_provider_models",
        lambda row: [{"id": "gpt-4o-mini", "name": "gpt-4o-mini", "provider": "openai", "owned_by": "openai", "created_at": None}],
    )

    result = list_central_models(provider="openai", db=_DB(credential), actor=actor)

    assert result["provider"] == "openai"
    assert result["models"][0]["id"] == "gpt-4o-mini"
    assert "api_key" not in result
    assert "sk-tenant-secret" not in str(result)


def test_endpoint_rejects_a_provider_different_from_the_central_credential():
    credential = SimpleNamespace(provider="claude", api_key="anthropic-tenant-secret")
    actor = SimpleNamespace(tenant_id="tenant-b")

    with pytest.raises(Exception) as exc_info:
        list_central_models(provider="openai", db=_DB(credential), actor=actor)

    assert getattr(exc_info.value, "status_code", None) == 409
