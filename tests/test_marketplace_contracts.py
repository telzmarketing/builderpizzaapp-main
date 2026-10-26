import pytest

from backend.services.marketplaces.contracts import (
    MarketplaceEventChannel,
    MarketplaceEventEnvelope,
    MarketplaceEventState,
    MarketplaceExternalPayment,
    MarketplaceExternalPaymentState,
    MarketplaceDeliverySnapshot,
    MarketplaceOrderOrigin,
    MarketplaceProvider,
    MarketplaceTenantBinding,
)
from backend.core.tenant_context import TenantContextError, TenantSource
from backend.services.marketplaces.tenant import resolve_marketplace_context


def make_tenant() -> MarketplaceTenantBinding:
    return MarketplaceTenantBinding(
        tenant_id="tenant-a",
        integration_id="integration-a",
        provider="iFood",
        external_merchant_id="merchant-a",
    )


def make_event(**overrides) -> MarketplaceEventEnvelope:
    values = {
        "event_id": "event-a",
        "order_id": "order-a",
        "event_type": "ORDER_CREATED",
        "tenant": make_tenant(),
        "channel": "webhook",
        "payload": {"provider_status": "PLACED", "items": [{"external_id": "item-a"}]},
    }
    values.update(overrides)
    return MarketplaceEventEnvelope(**values)


def test_contract_normalizes_provider_and_channel_without_accepting_store_origin():
    event = make_event()

    assert event.tenant.provider is MarketplaceProvider.IFOOD
    assert event.channel is MarketplaceEventChannel.WEBHOOK
    assert event.origin is MarketplaceOrderOrigin.MARKETPLACE
    assert event.state is MarketplaceEventState.RECEIVED


def test_contract_allows_event_without_order_id_before_detail_lookup():
    event = make_event(order_id=None)

    assert event.order_id is None
    assert event.event_id == "event-a"


def test_contract_supports_quarantine_state():
    event = make_event(state="quarantined")

    assert event.state is MarketplaceEventState.QUARANTINED


@pytest.mark.parametrize(
    "kwargs",
    [
        {"event_id": ""},
        {"order_id": ""},
        {"event_type": ""},
        {"tenant": None},
        {"channel": "unknown"},
        {"origin": "own_store"},
    ],
)
def test_contract_fails_closed_for_invalid_identity_or_origin(kwargs):
    with pytest.raises(ValueError):
        make_event(**kwargs)


@pytest.mark.parametrize("key", ["customer_id", "email", "phone", "address", "cpf"])
def test_contract_rejects_customer_or_pii_fields_recursively(key):
    with pytest.raises(ValueError, match="PII/customer field"):
        make_event(payload={"details": {key: "blocked"}})


def test_contract_payload_is_immutable_after_creation():
    event = make_event()

    with pytest.raises(TypeError):
        event.payload["new_key"] = "blocked"

    with pytest.raises(TypeError):
        event.payload["items"][0]["external_id"] = "changed"


def test_delivery_snapshot_is_separate_and_allowlisted():
    snapshot = MarketplaceDeliverySnapshot(
        recipient_name="Cliente Marketplace",
        phone="5511999999999",
        address_line="Rua A",
        address_number="10",
        complement="Apto 2",
        postal_code="01000000",
    )

    assert snapshot.recipient_name == "Cliente Marketplace"
    assert snapshot.phone == "5511999999999"

    with pytest.raises(TypeError):
        MarketplaceDeliverySnapshot(email="blocked")


def test_delivery_snapshot_does_not_relax_technical_payload_pii_block():
    with pytest.raises(ValueError, match="PII/customer field"):
        make_event(payload={"delivery": {"phone": "5511999999999"}})


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, MarketplaceExternalPaymentState.PENDING),
        ("pending", MarketplaceExternalPaymentState.PENDING),
        ("CONFIRMED", MarketplaceExternalPaymentState.CONFIRMED),
    ],
)
def test_external_payment_contract_has_no_gateway_and_explicit_state(value, expected):
    payment = MarketplaceExternalPayment(state=value or expected)

    assert payment.state is expected
    assert payment.external_reference is None


def test_delivery_snapshot_rejects_fields_outside_its_allowlist():
    with pytest.raises(TypeError):
        MarketplaceDeliverySnapshot(email="blocked")


def test_delivery_snapshot_rejects_non_string_values():
    with pytest.raises(ValueError):
        MarketplaceDeliverySnapshot(phone=123)


def test_external_marketplace_payment_never_models_local_gateway_charge():
    pending = MarketplaceExternalPayment()
    confirmed = MarketplaceExternalPayment(
        state="confirmed",
        external_reference="payment-a",
    )

    assert pending.state is MarketplaceExternalPaymentState.PENDING
    assert confirmed.state is MarketplaceExternalPaymentState.CONFIRMED
    assert confirmed.external_reference == "payment-a"


def test_external_marketplace_payment_supports_explicit_quarantine():
    payment = MarketplaceExternalPayment(state="quarantined")

    assert payment.state is MarketplaceExternalPaymentState.QUARANTINED


def test_marketplace_context_uses_server_owned_binding():
    context = resolve_marketplace_context(
        make_tenant(),
        source=TenantSource.WEBHOOK,
        configured_provider="ifood",
        configured_merchant_id="merchant-a",
        integration_active=True,
        correlation_id="corr-a",
    )

    assert context.tenant_id == "tenant-a"
    assert context.source is TenantSource.WEBHOOK
    assert context.correlation_id == "corr-a"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"source": TenantSource.PANEL},
        {"configured_provider": "keeta"},
        {"configured_merchant_id": "merchant-b"},
        {"integration_active": False},
    ],
)
def test_marketplace_context_fails_closed_on_binding_mismatch(kwargs):
    values = {
        "source": TenantSource.WEBHOOK,
        "configured_provider": "ifood",
        "configured_merchant_id": "merchant-a",
        "integration_active": True,
    }
    values.update(kwargs)
    with pytest.raises(TenantContextError):
        resolve_marketplace_context(make_tenant(), **values)

