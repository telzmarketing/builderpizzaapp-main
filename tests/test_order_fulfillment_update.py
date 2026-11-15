from types import SimpleNamespace

import pytest

from backend.main import app  # noqa: F401 - register the project's model graph
from backend.core.exceptions import DomainError
from backend.models.order import OrderStatus
from backend.services.order_service import OrderService


class FakeDb:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1

    def refresh(self, _value):
        pass


def make_order(**values):
    base = {
        "id": "order-1",
        "tenant_id": "tenant-1",
        "status": OrderStatus.pending,
        "fulfillment_type": "delivery",
        "sales_channel": "counter",
        "table_id": None,
        "table_session_id": None,
        "delivery": None,
        "payment": None,
        "updated_at": None,
    }
    base.update(values)
    return SimpleNamespace(**base)


def service_for(order):
    service = OrderService.__new__(OrderService)
    service._db = FakeDb()
    service._get_order = lambda _order_id: order
    return service


def test_pending_order_can_change_fulfillment_and_audits_change():
    order = make_order()
    service = service_for(order)

    updated = service.update_fulfillment_type("order-1", "pickup", changed_by="admin-1")

    assert updated.fulfillment_type == "pickup"
    assert service._db.commits == 1
    audit = service._db.added[0]
    assert audit.tenant_id == "tenant-1"
    assert audit.module_key == "pedidos"
    assert audit.old_value == "fulfillment_type=delivery"
    assert audit.new_value == "fulfillment_type=pickup"


@pytest.mark.parametrize("status", [OrderStatus.paid, OrderStatus.preparing, OrderStatus.delivered, OrderStatus.cancelled])
def test_advanced_or_terminal_order_cannot_change_fulfillment(status):
    order = make_order(status=status)
    service = service_for(order)

    with pytest.raises(DomainError) as error:
        service.update_fulfillment_type("order-1", "pickup", changed_by="admin-1")

    assert error.value.code == "OrderFulfillmentNotEditable"
    assert order.fulfillment_type == "delivery"
