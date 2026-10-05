from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_checkout_uses_tenant_webhook_url_when_rollout_is_enabled():
    source = (ROOT / "backend" / "services" / "payment_service.py").read_text(encoding="utf-8")

    assert "def _webhook_notification_url(self, provider: str)" in source
    assert "TENANT_PAYMENT_WEBHOOKS_ENABLED" in source
    assert "Webhook multiempresa exige tenant confiavel" in source
    assert "PaymentWebhookTenantResolver(" in source
    assert ".endpoint_key_for(self._tenant_id, provider)" in source
    assert 'return f"{base_url}/api/webhooks/{provider_path}/{endpoint_key}"' in source
    assert '"notification_url": self._webhook_notification_url(PROVIDER_MERCADO_PAGO)' in source
    assert '"notification_url": f"{base_url}/api/payments/webhook"' not in source


def test_webhook_catalog_can_return_endpoint_key_for_generation():
    source = (ROOT / "backend" / "services" / "payment_webhook_tenant_resolver.py").read_text(encoding="utf-8")

    assert "def endpoint_key_for(self, tenant_id: str, provider: str) -> str:" in source
    assert "binding.tenant_id == tenant_id and binding.provider == provider" in source
    assert "Endpoint de webhook nao configurado para o tenant." in source
