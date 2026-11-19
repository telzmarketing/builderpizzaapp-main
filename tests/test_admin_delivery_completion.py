from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core.exceptions import DomainError
from backend.models.delivery import DeliveryStatus
from backend.schemas.delivery import DeliveryAdminCompleteIn
from backend.services.delivery_service import DeliveryService


ROOT = Path(__file__).resolve().parents[1]


def test_admin_completion_schema_requires_non_blank_reason():
    assert DeliveryAdminCompleteIn(reason="  cliente confirmou por telefone  ").reason == (
        "cliente confirmou por telefone"
    )
    with pytest.raises(ValueError):
        DeliveryAdminCompleteIn(reason="   ")


def _service_for_admin_completion(status=DeliveryStatus.assigned):
    delivery = SimpleNamespace(
        id="delivery-1", order_id="order-1", delivery_person_id="driver-1", status=status
    )
    events = []
    transitions = []
    service = DeliveryService.__new__(DeliveryService)
    service._db = SimpleNamespace(commit=lambda: None, refresh=lambda _row: None)
    service._get_delivery_for_completion = lambda _delivery_id: delivery

    def update_status(_delivery_id, next_status):
        transitions.append(next_status)
        delivery.status = DeliveryStatus(next_status)
        return delivery

    def complete(_delivery_id, **_kwargs):
        delivery.status = DeliveryStatus.completed
        return delivery

    service.update_status = update_status
    service.complete = complete
    service._add_event = lambda *args, **kwargs: events.append((args, kwargs))
    return service, delivery, transitions, events


def test_admin_completion_walks_state_machine_and_records_audited_action():
    service, delivery, transitions, events = _service_for_admin_completion()

    result = service.admin_complete(
        "delivery-1",
        reason="Cliente confirmou a entrega por telefone",
        actor_id="admin-1",
        recipient_name="Maria",
        delivery_photo_url="https://example.test/proof.jpg",
    )

    assert result is delivery
    assert delivery.status == DeliveryStatus.completed
    assert transitions == ["picked_up", "on_the_way", "delivered"]
    assert events[0][0] == ("delivery-1", "admin_completed")
    assert events[0][1]["actor_type"] == "admin"
    assert events[0][1]["actor_id"] == "admin-1"
    assert events[0][1]["metadata"]["from_status"] == "assigned"
    assert events[0][1]["metadata"]["to_status"] == "completed"
    assert events[0][1]["metadata"]["reason"] == "Cliente confirmou a entrega por telefone"


def test_admin_completion_is_idempotent_for_completed_delivery():
    service, delivery, transitions, events = _service_for_admin_completion(DeliveryStatus.completed)
    complete_calls = []

    def complete(_delivery_id, **_kwargs):
        complete_calls.append(True)
        return delivery

    service.complete = complete

    assert service.admin_complete("delivery-1", reason="Retry", actor_id="admin-1") is delivery
    assert transitions == []
    assert complete_calls == [True]
    assert events == []


def test_admin_completion_blocks_failed_and_cancelled():
    for status in (DeliveryStatus.failed, DeliveryStatus.cancelled):
        service, _delivery, transitions, _events = _service_for_admin_completion(status)
        with pytest.raises(DomainError) as error:
            service.admin_complete("delivery-1", reason="Confirmed", actor_id="admin-1")
        assert error.value.code == "DeliveryNotActive"
        assert transitions == []


def test_admin_completion_route_is_rbac_protected_and_service_is_tenant_scoped():
    route = (ROOT / "backend/routes/delivery.py").read_text(encoding="utf-8")
    service = (ROOT / "backend/services/delivery_service.py").read_text(encoding="utf-8")

    assert '@router.post("/{delivery_id}/admin-complete")' in route
    assert 'Depends(require_rbac_permission("pedidos", "edit"))' in route
    assert ".admin_complete(" in route
    assert "self._get_delivery_for_completion(delivery_id)" in service
    assert 'actor_type="admin"' in service
    assert '"reason": reason' in service
    assert "self.update_status(delivery_id, next_status)" in service
