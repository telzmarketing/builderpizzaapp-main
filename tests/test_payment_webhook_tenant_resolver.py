import pytest

from backend.services.payment_webhook_tenant_resolver import PaymentWebhookTenantResolutionError, parse_endpoint_catalog

KEY = "tenant_endpoint_key_1234567890"

def test_catalog_accepts_one_opaque_binding_per_tenant_provider():
    catalog = parse_endpoint_catalog('{"%s":{"tenant_id":"tenant-a","provider":"mercado_pago"}}' % KEY)
    assert catalog[KEY].tenant_id == "tenant-a"

@pytest.mark.parametrize("raw", ["not-json", "[]", '{"short":{"tenant_id":"a","provider":"asaas"}}'])
def test_catalog_rejects_invalid_configuration(raw):
    with pytest.raises(PaymentWebhookTenantResolutionError):
        parse_endpoint_catalog(raw)

def test_catalog_rejects_multiple_keys_for_same_binding():
    raw = ('{"tenant_endpoint_key_1234567890":{"tenant_id":"tenant-a","provider":"asaas"},'
           '"tenant_endpoint_key_0987654321":{"tenant_id":"tenant-a","provider":"asaas"}}')
    with pytest.raises(PaymentWebhookTenantResolutionError):
        parse_endpoint_catalog(raw)
