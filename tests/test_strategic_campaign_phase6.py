from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.services.payment_service import PaymentService


def test_future_scheduled_order_defers_inventory_consumption():
    order = SimpleNamespace(
        is_scheduled=True,
        scheduled_for=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    assert PaymentService._scheduled_order_not_due(order) is True


def test_due_scheduled_order_can_enter_operational_consumption():
    order = SimpleNamespace(
        is_scheduled=True,
        scheduled_for=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    assert PaymentService._scheduled_order_not_due(order) is False


def test_non_scheduled_order_keeps_existing_payment_behavior():
    order = SimpleNamespace(is_scheduled=False, scheduled_for=None)
    assert PaymentService._scheduled_order_not_due(order) is False
