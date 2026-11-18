from pathlib import Path

import pytest

from backend.core.exceptions import DomainError
from backend.models.delivery import DeliveryStatus
from backend.models.payment import PaymentStatus
from backend.schemas.delivery import DeliveryConfirmIn
from backend.services.delivery_service import DeliveryService


ROOT = Path(__file__).resolve().parents[1]


def test_delivery_confirmation_schema_accepts_only_four_digits():
    assert DeliveryConfirmIn(code="0427").code == "0427"
    with pytest.raises(ValueError):
        DeliveryConfirmIn(code="42ab")


def _completion_service(*, status=DeliveryStatus.on_the_way, driver_id="driver-1", payment=None):
    service = DeliveryService.__new__(DeliveryService)
    delivery = type(
        "DeliveryFixture",
        (),
        {
            "id": "delivery-1",
            "order_id": "order-1",
            "delivery_person_id": driver_id,
            "status": status,
            "confirmation_code": "0427",
            "confirmed_by_code_at": None,
        },
    )()
    service._get_delivery_person = lambda _person_id: object()
    service._get_delivery_for_completion = lambda _delivery_id: delivery
    events = []
    calls = []
    service._add_event = lambda *args, **kwargs: events.append((args, kwargs))
    service._get_order = lambda _order_id: type("OrderFixture", (), {"payment": payment})()

    def mark_delivered(_person_id, _delivery_id, notes=None):
        calls.append("delivered")
        delivery.status = DeliveryStatus.delivered
        return delivery

    def complete(_delivery_id, **kwargs):
        calls.append("completed")
        delivery.status = DeliveryStatus.completed
        return delivery

    service.mark_driver_delivered = mark_delivered
    service.complete = complete
    service._db = type(
        "DbFixture",
        (),
        {"commit": lambda self: None, "refresh": lambda self, _row: None},
    )()

    return service, delivery, calls, events


def test_driver_completion_needs_no_code_and_retry_does_not_repeat_completion():
    service, delivery, calls, events = _completion_service()
    completed = service.complete_driver_delivery("driver-1", "delivery-1")
    retried = service.complete_driver_delivery("driver-1", "delivery-1")

    assert completed is delivery
    assert retried is delivery
    assert calls == ["delivered", "completed"]
    assert len(events) == 1
    assert events[0][0][1] == "driver_completed"
    assert delivery.confirmation_code == "0427"
    assert delivery.confirmed_by_code_at is None


def test_driver_completion_keeps_ownership_and_route_gate():
    service, delivery, calls, _events = _completion_service(driver_id="driver-2")
    with pytest.raises(DomainError) as error:
        service.complete_driver_delivery("driver-1", "delivery-1")
    assert error.value.code == "DeliveryOwnershipDenied"
    assert calls == []

    delivery.delivery_person_id = "driver-1"
    delivery.status = DeliveryStatus.assigned
    with pytest.raises(DomainError) as error:
        service.complete_driver_delivery("driver-1", "delivery-1")
    assert error.value.code == "DeliveryNotInRoute"
    assert calls == []


def test_driver_completion_keeps_payment_receipt_gate():
    payment = type("PaymentFixture", (), {"pay_on_delivery": True, "status": PaymentStatus.pending})()
    service, delivery, calls, _events = _completion_service(payment=payment)
    with pytest.raises(DomainError) as error:
        service.complete_driver_delivery("driver-1", "delivery-1")
    assert error.value.code == "PaymentReceiptRequired"
    assert calls == []

    payment.status = PaymentStatus.approved
    assert service.complete_driver_delivery("driver-1", "delivery-1") is delivery
    assert calls == ["delivered", "completed"]


def test_phase9_backend_contract_keeps_audit_gate_and_dispatch_order():
    delivery = (ROOT / "backend/services/delivery_service.py").read_text(encoding="utf-8")
    kds = (ROOT / "backend/services/kds_service.py").read_text(encoding="utf-8")
    audit = (ROOT / "backend/services/kds_audit_service.py").read_text(encoding="utf-8")

    start = delivery[
        delivery.index("    def start_driver_delivery(") :
        delivery.index("    def mark_driver_delivered(")
    ]
    complete = delivery[
        delivery.index("    def complete_driver_delivery(") :
        delivery.index("    def report_driver_problem(")
    ]
    assert 'code="DeliveryAuditRequired"' in start
    assert 'audit.status != "completed"' in start
    assert 'code="DeliveryConfirmationCodeRequired"' not in complete
    assert "self._confirm_delivery_code_locked" not in complete
    assert "random.choices" not in delivery
    assert "random.choices" not in kds
    assert "confirmation_code=payload.confirmation_code" in (
        ROOT / "backend/routes/delivery.py"
    ).read_text(encoding="utf-8")

    dispatch = kds[
        kds.index("    def check_oven_in_dispatch(") :
        kds.index("    def complete_dispatch_unit(")
    ]
    packaging = kds[
        kds.index("    def complete_dispatch_unit(") :
        kds.index("    def _auto_assign_order(")
    ]
    assert "old_unit_state = unit.state" in dispatch
    assert "old_attempt_state = attempt.state if attempt is not None else None" in dispatch
    assert "self._oven_check_is_eligible(old_unit_state, old_attempt_state)" in dispatch
    assert '"baking", "checking"' in kds[kds.index("    def _oven_check_is_eligible(") : kds.index("    def kitchen_orders(")]
    assert '"ready"' in dispatch
    assert "OrderStatus.preparing.value" in packaging
    assert "OrderStatus.ready_for_pickup.value" in packaging
    assert "DispatchOrderNotReady" in packaging
    assert "self._assert_all_units_ready(order)" not in packaging
    assert 'unit.state != "ready"' in packaging
    assert 'if all_closed and order.fulfillment_type == "delivery"' in packaging
    assert 'changed_by=f"kds:expedicao:{actor_id}"' in dispatch
    assert "self._auto_assign_order" in packaging
    assert "dispatch_completed_at" in packaging
    assert "DeliveryStatus.pending_assignment, DeliveryStatus.assigned" in audit
    assert "audit.status, audit.completed_at" in audit
