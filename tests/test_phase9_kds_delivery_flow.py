from pathlib import Path

import pytest

from backend.core.exceptions import DomainError
from backend.models.delivery import DeliveryStatus
from backend.schemas.delivery import DeliveryConfirmIn
from backend.services.delivery_service import DeliveryService


ROOT = Path(__file__).resolve().parents[1]


def test_delivery_confirmation_schema_accepts_only_four_digits():
    assert DeliveryConfirmIn(code="0427").code == "0427"
    with pytest.raises(ValueError):
        DeliveryConfirmIn(code="42ab")


def test_driver_completion_requires_customer_code_before_finishing():
    service = DeliveryService.__new__(DeliveryService)
    delivery = type(
        "DeliveryFixture",
        (),
        {
            "delivery_person_id": "driver-1",
            "status": DeliveryStatus.delivered,
            "confirmed_by_code_at": None,
        },
    )()
    service._get_delivery_person = lambda _person_id: object()
    service._get_delivery_for_completion = lambda _delivery_id: delivery

    with pytest.raises(DomainError) as error:
        service.complete_driver_delivery("driver-1", "delivery-1")

    assert error.value.code == "DeliveryConfirmationCodeRequired"


def test_driver_completion_validates_code_in_the_same_command():
    service = DeliveryService.__new__(DeliveryService)
    delivery = type(
        "DeliveryFixture",
        (),
        {
            "id": "delivery-1",
            "order_id": "order-1",
            "delivery_person_id": "driver-1",
            "status": DeliveryStatus.on_the_way,
            "confirmation_code": "0427",
            "confirmed_by_code_at": None,
        },
    )()
    service._get_delivery_person = lambda _person_id: object()
    service._get_delivery_for_completion = lambda _delivery_id: delivery
    service._add_event = lambda *args, **kwargs: None
    service._get_order = lambda _order_id: type("OrderFixture", (), {"payment": None})()
    service.mark_driver_delivered = lambda _person_id, _delivery_id, notes=None: delivery
    service.complete = lambda _delivery_id, **kwargs: delivery
    service._db = type(
        "DbFixture",
        (),
        {"commit": lambda self: None, "refresh": lambda self, _row: None},
    )()

    completed = service.complete_driver_delivery(
        "driver-1",
        "delivery-1",
        confirmation_code="0427",
    )

    assert completed is delivery
    assert delivery.confirmed_by_code_at is not None


def test_driver_completion_rejects_invalid_code_without_confirming():
    service = DeliveryService.__new__(DeliveryService)
    delivery = type(
        "DeliveryFixture",
        (),
        {
            "id": "delivery-1",
            "order_id": "order-1",
            "delivery_person_id": "driver-1",
            "status": DeliveryStatus.on_the_way,
            "confirmation_code": "0427",
            "confirmed_by_code_at": None,
        },
    )()
    service._get_delivery_person = lambda _person_id: object()
    service._get_delivery_for_completion = lambda _delivery_id: delivery

    with pytest.raises(DomainError) as error:
        service.complete_driver_delivery(
            "driver-1",
            "delivery-1",
            confirmation_code="9999",
        )

    assert error.value.code == "InvalidCode"
    assert delivery.confirmed_by_code_at is None


def test_phase9_backend_contract_keeps_audit_gate_and_dispatch_order():
    delivery = (ROOT / "backend/services/delivery_service.py").read_text(encoding="utf-8")
    kds = (ROOT / "backend/services/kds_service.py").read_text(encoding="utf-8")
    audit = (ROOT / "backend/services/kds_audit_service.py").read_text(encoding="utf-8")
    motoboy = (ROOT / "client/pages/Motoboy.tsx").read_text(encoding="utf-8")
    api = (ROOT / "client/lib/api.ts").read_text(encoding="utf-8")

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
    assert 'code="DeliveryConfirmationCodeRequired"' in complete
    assert "confirmation_code=payload.confirmation_code" in (
        ROOT / "backend/routes/delivery.py"
    ).read_text(encoding="utf-8")
    assert "deliveryApi.driverCompleteDelivery(d.id, code)" in motoboy
    assert "await deliveryApi.confirmCode(d.id, code)" not in motoboy
    assert "{ confirmation_code, notes, payment_received }" in api

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
