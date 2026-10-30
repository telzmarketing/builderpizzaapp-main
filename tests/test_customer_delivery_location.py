from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.core.exceptions import OrderNotFound
from backend.models.delivery import DeliveryStatus
from backend.models.order import Order
from backend.models.delivery import Delivery, DeliveryPerson
from backend.services.delivery_service import DeliveryService


class _Query:
    def __init__(self, row):
        self.row = row

    def filter(self, *_conditions):
        return self

    def first(self):
        return self.row


class _Db:
    def __init__(self, *, order=None, delivery=None, person=None):
        self.rows = {Order: order, Delivery: delivery, DeliveryPerson: person}

    def query(self, model):
        return _Query(self.rows.get(model))


def _service(order, delivery, person):
    return DeliveryService(
        _Db(order=order, delivery=delivery, person=person),
        tenant_id="tenant-a",
    )


def test_customer_location_returns_only_recent_position_for_own_active_order():
    order = SimpleNamespace(id="order-a", customer_id="customer-a")
    delivery = SimpleNamespace(
        order_id="order-a",
        delivery_person_id="person-a",
        status=DeliveryStatus.on_the_way,
    )
    person = SimpleNamespace(
        location_lat=-23.5505,
        location_lng=-46.6333,
        location_updated_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )

    result = _service(order, delivery, person).get_customer_location("order-a", "customer-a")

    assert result["available"] is True
    assert result["latitude"] == -23.5505
    assert result["longitude"] == -46.6333
    assert "delivery_person_id" not in result


def test_customer_location_hides_stale_position_and_inactive_delivery():
    order = SimpleNamespace(id="order-a", customer_id="customer-a")
    stale_person = SimpleNamespace(
        location_lat=-23.5,
        location_lng=-46.6,
        location_updated_at=datetime.now(timezone.utc) - timedelta(seconds=121),
    )
    stale_delivery = SimpleNamespace(
        order_id="order-a",
        delivery_person_id="person-a",
        status=DeliveryStatus.on_the_way,
    )

    stale = _service(order, stale_delivery, stale_person).get_customer_location("order-a", "customer-a")
    assert stale["available"] is False
    assert stale["latitude"] is None

    inactive_delivery = SimpleNamespace(
        order_id="order-a",
        delivery_person_id="person-a",
        status=DeliveryStatus.assigned,
    )
    inactive = _service(order, inactive_delivery, stale_person).get_customer_location("order-a", "customer-a")
    assert inactive["available"] is False
    assert inactive["delivery_status"] == DeliveryStatus.assigned


def test_customer_location_does_not_find_another_customers_order():
    with pytest.raises(OrderNotFound):
        _service(None, None, None).get_customer_location("order-a", "customer-b")
