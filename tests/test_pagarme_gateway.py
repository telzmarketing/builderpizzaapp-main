import hashlib
import hmac
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.models.payment import PaymentMethod
from backend.schemas.payment import PaymentCreate
from backend.services.pagarme_client import sanitize_pagarme_payload, verify_pagarme_signature
from backend.services.pagarme_gateway import PagarmeGateway
from backend.services.payment_gateway_resolver import PaymentGatewayResolver


def config(**overrides):
    values = dict(
        pagarme_enabled=True, pagarme_environment="sandbox",
        pagarme_public_key="pk_test", pagarme_secret_key="sk_test",
        pagarme_webhook_secret="hook_secret", pagarme_pix_enabled=True,
        pagarme_credit_card_enabled=True, pagarme_max_installments=6,
        accept_pix=True, accept_credit_card=True, accept_debit_card=False,
        accept_cash=True, pix_provider="pagarme", credit_card_provider="pagarme",
        mp_enabled=False, mp_environment="sandbox", mp_public_key=None,
        mp_pix_enabled=False, mp_credit_card_enabled=False, mp_max_installments=1,
        asaas_enabled=False, asaas_environment="sandbox", asaas_api_key=None,
        asaas_pix_enabled=False, asaas_credit_card_enabled=False,
        asaas_max_installments=1, asaas_tokenization_status="not_validated",
    )
    values.update(overrides)
    values.update(id="pgc-a", tenant_id="tenant-a")
    return SimpleNamespace(**values)


def test_resolver_exposes_pagarme_only_when_tenant_config_is_ready():
    resolver = PaymentGatewayResolver(config())
    assert resolver.resolve(PaymentMethod.pix).enabled is True
    assert resolver.resolve(PaymentMethod.credit_card).enabled is True
    assert resolver.public_config()["providers"]["pagarme"]["public_key"] == "pk_test"
    assert PaymentGatewayResolver(config(pagarme_secret_key=None)).resolve(PaymentMethod.pix).enabled is False


def test_card_contract_rejects_pan_and_accepts_token():
    with pytest.raises(ValidationError):
        PaymentCreate(order_id="o", payment_method="credit_card", formData={"card": {"number": "4000000000000010"}})
    parsed = PaymentCreate(order_id="o", payment_method="credit_card", token="token_test", installments=2)
    assert parsed.token == "token_test"


def test_gateway_sends_token_but_never_pan_or_cvv():
    class Client:
        def create_order(self, payload, *, idempotency_key):
            self.payload, self.key = payload, idempotency_key
            return {"id": "or_1", "status": "pending", "charges": []}
    client = Client()
    gateway = PagarmeGateway(config(), client=client)
    customer = SimpleNamespace(name="Cliente", email="c@example.com", phone="11999999999")
    order = SimpleNamespace(id="order-1", tenant_id="tenant-a", customer=customer)
    payment = SimpleNamespace(method=PaymentMethod.credit_card, amount=10.5)
    gateway.create(order, payment, token="token_test", installments=2, document="12345678901")
    card = client.payload["payments"][0]["credit_card"]
    assert card["card_token"] == "token_test"
    assert "number" not in card
    assert "cvv" not in card
    assert len(client.key) == 64


def test_webhook_signature_is_fail_closed_and_constant_contract():
    body = b'{"id":"hook_1"}'
    signature = hmac.new(b"secret", body, hashlib.sha1).hexdigest()
    assert verify_pagarme_signature(body, f"sha1={signature}", "secret") is True
    assert verify_pagarme_signature(body, signature, "wrong") is False
    assert verify_pagarme_signature(body, None, "secret") is False


def test_sanitizer_masks_card_token_recursively():
    payload = sanitize_pagarme_payload({"payments": [{"credit_card": {"card_token": "token_x"}}]})
    assert payload["payments"][0]["credit_card"]["card_token"] == "***"
