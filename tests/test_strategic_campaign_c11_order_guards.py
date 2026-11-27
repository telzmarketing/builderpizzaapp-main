from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.core.exceptions import DomainError
from backend.core.events import OrderStatusChanged
from backend.models.order import OrderStatus
from backend.models.strategic_campaign import StrategicOffer
from backend.schemas.order import CartItemIn
from backend.services.order_service import OrderService
from backend.services.strategic_offer_composition_service import ResolvedStrategicGroup


def _payload(*, scheduled=False, scheduled_for=None, payment_method="pix"):
    return SimpleNamespace(
        delivery=SimpleNamespace(
            is_scheduled=scheduled,
            scheduled_for=scheduled_for,
        ),
        payment_method=payment_method,
    )


def _campaign(**config):
    return SimpleNamespace(
        id=config.pop("id", "campaign-1"),
        starts_at=config.pop("starts_at", None),
        ends_at=config.pop("ends_at", None),
        commercial_config=config,
    )


def _resolved_group(*, strategy, quantity=2, amount=Decimal("10.00")):
    offer = StrategicOffer(pricing_strategy=strategy)
    if strategy == "fixed_price":
        offer.fixed_promotional_price = amount
    elif strategy == "fixed_discount":
        offer.discount_amount = amount
    return SimpleNamespace(
        request=SimpleNamespace(
            quantity=quantity,
            campaign_version=1,
            composition_revision=1,
            selections=[],
        ),
        offer=offer,
        campaign=SimpleNamespace(id="campaign-1"),
        item_start=0,
        item_count=quantity * 2,
        step_subcategories=("pizza", "drink") * quantity,
    )


def test_group_campaign_requires_canonical_preorder_schedule():
    contexts = [(_campaign(sales_mode="preorder"), SimpleNamespace())]

    with pytest.raises(DomainError) as error:
        OrderService._validate_strategic_commercial_rules(_payload(), contexts)

    assert error.value.code == "StrategicScheduleRequired"


def test_all_group_campaigns_apply_payment_rules():
    contexts = [
        (_campaign(id="campaign-1", allowed_payment_methods=["pix"]), SimpleNamespace()),
        (_campaign(id="campaign-2", allowed_payment_methods=["credit_card"]), SimpleNamespace()),
    ]

    with pytest.raises(DomainError) as error:
        OrderService._validate_strategic_commercial_rules(
            _payload(payment_method="pix"), contexts,
        )

    assert error.value.code == "StrategicPaymentMethodNotAllowed"


def test_future_group_campaign_fails_closed():
    contexts = [(
        _campaign(starts_at=datetime.now(timezone.utc) + timedelta(hours=1)),
        SimpleNamespace(),
    )]

    with pytest.raises(DomainError) as error:
        OrderService._validate_strategic_commercial_rules(_payload(), contexts)

    assert error.value.code == "StrategicCampaignUnavailable"


def test_closed_store_requires_every_group_campaign_to_allow_it():
    contexts = [
        (_campaign(id="campaign-1", allow_when_store_closed=True), SimpleNamespace()),
        (_campaign(id="campaign-2", allow_when_store_closed=False), SimpleNamespace()),
    ]

    assert OrderService._strategic_allows_closed_store(contexts) is False


@pytest.mark.parametrize(
    ("strategy", "amount", "expected_promotional", "expected_discount"),
    [
        ("fixed_price", Decimal("79.90"), Decimal("159.80"), Decimal("40.20")),
        ("fixed_discount", Decimal("10.00"), Decimal("180.00"), Decimal("20.00")),
    ],
)
def test_fixed_pricing_is_applied_once_per_commercial_unit(
    strategy, amount, expected_promotional, expected_discount,
):
    documents, discount = OrderService._quote_strategic_groups(
        [_resolved_group(strategy=strategy, amount=amount)],
        [Decimal("50.00")] * 4,
    )

    assert documents[0]["original_amount"] == Decimal("200.00")
    assert documents[0]["promotional_amount"] == expected_promotional
    assert discount == expected_discount


def test_fixed_promotional_price_preserves_paid_additions():
    documents, discount = OrderService._quote_strategic_groups(
        [_resolved_group(strategy="fixed_price", amount=Decimal("79.90"))],
        [Decimal("55.00"), Decimal("50.00"), Decimal("55.00"), Decimal("50.00")],
        [Decimal("5.00"), Decimal("0.00"), Decimal("5.00"), Decimal("0.00")],
    )

    assert documents[0]["original_amount"] == Decimal("210.00")
    assert documents[0]["promotional_amount"] == Decimal("169.80")
    assert discount == Decimal("40.20")


def test_confirmed_reservation_is_bound_inside_order_transaction():
    reservation = SimpleNamespace(
        id="reservation-1",
        offer_id="offer-1",
        quantity=2,
        customer_reference="customer-1",
        status="confirmed",
        order_id=None,
    )

    class Query:
        def filter(self, *_args): return self
        def with_for_update(self): return self
        def first(self): return reservation

    service = OrderService.__new__(OrderService)
    service._db = SimpleNamespace(query=lambda _model: Query())
    service._tenant_context = SimpleNamespace(tenant_id="tenant-1")
    payload = SimpleNamespace(
        reservation_id="reservation-1",
        customer_id="customer-1",
        items=[],
    )
    group = SimpleNamespace(
        offer=SimpleNamespace(id="offer-1"),
        request=SimpleNamespace(quantity=2),
    )

    service._bind_checkout_reservation(payload, SimpleNamespace(id="order-1"), None, [group])

    assert reservation.order_id == "order-1"


def test_strategic_kit_expansion_remaps_every_physical_item_to_commercial_group(monkeypatch):
    kit_line = CartItemIn(kit_id="kit-1", quantity=1, final_price=80)
    pizza = CartItemIn(product_id="pizza-1", quantity=1, final_price=60)
    drink = CartItemIn(product_id="drink-1", quantity=1, final_price=20)
    request = SimpleNamespace(
        quantity=1,
        campaign_version=1,
        composition_revision=1,
        selections=[],
    )
    group = ResolvedStrategicGroup(
        request=request,
        campaign=SimpleNamespace(id="campaign-1"),
        offer=StrategicOffer(id="offer-1", pricing_strategy="catalog"),
        item_start=0,
        item_count=1,
        step_subcategories=(None,),
    )
    component_metadata = {
        id(pizza): SimpleNamespace(unit_price=60, kit_id="kit-1", kit_name="Kit"),
        id(drink): SimpleNamespace(unit_price=20, kit_id="kit-1", kit_name="Kit"),
    }
    monkeypatch.setattr(
        "backend.services.order_service.ComboService.expand",
        lambda _self, _items: ([pizza, drink], component_metadata),
    )
    service = OrderService.__new__(OrderService)
    service._db = SimpleNamespace()
    service._tenant_context = SimpleNamespace(tenant_id="tenant-1")

    expanded, metadata, remapped = service._expand_combo_items([kit_line], [group])
    documents, _ = service._quote_strategic_groups(remapped, [Decimal("60"), Decimal("20")])

    assert expanded == [pizza, drink]
    assert metadata == component_metadata
    assert remapped[0].item_start == 0
    assert remapped[0].item_count == 2
    assert remapped[0].step_subcategories == (None, None)
    assert documents[0]["item_count"] == 2


def test_legacy_strategic_kit_consumes_limit_by_commercial_quantity(monkeypatch):
    calls = []
    service = OrderService.__new__(OrderService)
    service._db = SimpleNamespace()
    service._tenant_context = SimpleNamespace(tenant_id="tenant-1")
    offer = StrategicOffer(id="offer-kit")
    payload = SimpleNamespace(
        items=[CartItemIn(kit_id="kit-1", quantity=3, final_price=80)],
        customer_id="customer-1",
    )
    monkeypatch.setattr(
        "backend.services.strategic_offer_composition_service.StrategicOfferCompositionService._assert_purchase_limits",
        lambda _self, checked_offer, quantity, customer_id, **_: calls.append(
            (checked_offer.id, quantity, customer_id)
        ),
    )

    service._assert_legacy_strategic_purchase_limit(
        (SimpleNamespace(), offer), payload, consume_limits=False,
    )

    assert calls == [("offer-kit", 3, "customer-1")]


@pytest.mark.parametrize("terminal_status", ["cancelled", "refunded"])
def test_terminal_status_releases_redemption_and_reservation_before_one_commit(
    monkeypatch, terminal_status,
):
    calls = []
    order = SimpleNamespace(
        id="order-1",
        tenant_id="tenant-1",
        customer_id="customer-1",
        fulfillment_type="delivery",
        status=OrderStatus.paid,
        updated_at=None,
        paid_at=None,
        preparation_started_at=None,
        ready_for_pickup_at=None,
        out_for_delivery_at=None,
        delivered_at=None,
    )
    db = SimpleNamespace(
        flush=lambda: calls.append("flush"),
        commit=lambda: calls.append("commit"),
        refresh=lambda _: calls.append("refresh"),
    )
    service = OrderService.__new__(OrderService)
    service._db = db
    service._tenant_context = None
    monkeypatch.setattr(service, "_get_order", lambda *_args, **_kwargs: order)
    monkeypatch.setattr(
        "backend.services.order_service.order_sm.transition",
        lambda *_args: calls.append("transition"),
    )
    monkeypatch.setattr(
        service,
        "_reverse_inventory_for_cancelled_sale",
        lambda *_args: calls.append("inventory"),
    )
    monkeypatch.setattr(
        service,
        "_release_strategic_redemptions",
        lambda _order, *, status: calls.append(f"redemption:{status}"),
    )
    monkeypatch.setattr(
        "backend.services.strategic_campaign_capacity_service.StrategicCampaignCapacityService.release_for_cancelled_order",
        lambda *_args, **_kwargs: calls.append("reservation"),
    )
    monkeypatch.setattr(
        "backend.services.order_service.sync_customer_order_metrics",
        lambda *_args, **_kwargs: calls.append("metrics"),
    )
    monkeypatch.setattr(
        "backend.services.automation_event_producer.AutomationEventProducer.order_status_changed",
        lambda *_args, **_kwargs: calls.append("automation"),
    )
    monkeypatch.setattr(
        "backend.services.order_service.bus.publish",
        lambda *_args, **_kwargs: calls.append("publish"),
    )

    result = service.change_status("order-1", terminal_status)

    assert result is order
    assert calls.count("commit") == 1
    assert calls.index(f"redemption:{terminal_status}") < calls.index("commit")
    assert calls.index("reservation") < calls.index("commit")
    assert calls.index("commit") < calls.index("publish")


def test_cancel_defers_status_event_until_atomic_commit(monkeypatch):
    calls = []
    order = SimpleNamespace(
        id="order-1",
        tenant_id="tenant-1",
        payment=None,
        cancelled_by=None,
        cancellation_reason=None,
        cancelled_at=None,
    )
    db = SimpleNamespace(
        flush=lambda: calls.append("flush"),
        commit=lambda: calls.append("commit"),
        rollback=lambda: calls.append("rollback"),
        refresh=lambda _: calls.append("refresh"),
    )
    service = OrderService.__new__(OrderService)
    service._db = db
    service._tenant_context = None

    def change_status(_order_id, _status, **kwargs):
        kwargs["_event_sink"].append(OrderStatusChanged(
            order_id="order-1",
            from_status="paid",
            to_status="cancelled",
            changed_by="system",
            tenant_id="tenant-1",
        ))
        return order

    monkeypatch.setattr(service, "change_status", change_status)
    monkeypatch.setattr(
        "backend.services.kds_production_service.KdsProductionService.cancel_for_order",
        lambda *_args, **_kwargs: calls.append("kds"),
    )
    monkeypatch.setattr(
        "backend.services.order_service.bus.publish",
        lambda event: calls.append(type(event).__name__),
    )

    service.cancel("order-1", reason="cliente solicitou")

    assert calls.count("commit") == 1
    assert "rollback" not in calls
    assert calls.index("kds") < calls.index("commit")
    assert calls.index("commit") < calls.index("OrderStatusChanged")

