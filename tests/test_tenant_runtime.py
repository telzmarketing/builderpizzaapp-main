from types import SimpleNamespace

from backend.core import tenant_runtime


class ExplodingRequest:
    @property
    def headers(self):
        raise AssertionError("flags OFF nao devem ler headers nem consultar tenant")


def test_panel_resolution_preserves_legacy_when_auth_flag_is_off(monkeypatch):
    monkeypatch.setattr(
        tenant_runtime,
        "get_settings",
        lambda: SimpleNamespace(MULTI_TENANT_AUTH_ENABLED=False),
    )
    assert tenant_runtime.resolve_panel_tenant_context(ExplodingRequest(), object(), object()) is None


def test_public_resolution_preserves_legacy_when_domain_flag_is_off(monkeypatch):
    monkeypatch.setattr(
        tenant_runtime,
        "get_settings",
        lambda: SimpleNamespace(TENANT_DOMAINS_ENABLED=False),
    )
    assert tenant_runtime.resolve_public_tenant_context(ExplodingRequest(), object()) is None
