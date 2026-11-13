from types import SimpleNamespace

from backend.services import payment_service


def test_mercado_pago_tenant_token_never_falls_back_to_global(monkeypatch):
    monkeypatch.setattr(payment_service.settings, "MERCADO_PAGO_ACCESS_TOKEN", "global-token")
    tenant_config = SimpleNamespace(mp_access_token="tenant-token")

    assert payment_service._mp_token(tenant_config, tenant_scoped=True) == "tenant-token"


def test_mercado_pago_legacy_token_keeps_global_compatibility(monkeypatch):
    monkeypatch.setattr(payment_service.settings, "MERCADO_PAGO_ACCESS_TOKEN", "global-token")
    legacy_config = SimpleNamespace(mp_access_token=None)

    assert payment_service._mp_token(legacy_config) == "global-token"


def test_public_key_is_tenant_scoped_when_service_has_tenant(monkeypatch):
    monkeypatch.setattr(payment_service.settings, "MERCADO_PAGO_PUBLIC_KEY", "global-public")
    service = payment_service.PaymentService(object(), tenant_id="tenant-a")
    service._config = SimpleNamespace(mp_public_key="tenant-public")

    assert service.public_key() == {"public_key": "tenant-public"}
