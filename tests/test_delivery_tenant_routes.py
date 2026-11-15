from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core.exceptions import DomainError
from backend.models.delivery import DeliveryStatus, DeliveryPersonStatus
from backend.routes.delivery import _driver_login_service
from backend.services.delivery_service import DeliveryService


ROUTE = Path("backend/routes/delivery.py")
SERVICE = Path("backend/services/delivery_service.py")


def test_delivery_routes_do_not_instantiate_global_service() -> None:
    source = ROUTE.read_text(encoding="utf-8")

    assert "DeliveryService(db)" not in source
    assert "_admin_service(request, db, admin)" in source
    assert "_driver_service(db, person_id)" in source
    assert "_delivery_service(db, delivery_id)" in source


def test_driver_login_is_tenant_scoped_before_password_check() -> None:
    route = ROUTE.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")

    assert "resolve_public_tenant_context(request, db)" in route
    assert "_driver_login_service(db, body.email, tenant_context).driver_login" in route
    assert ".limit(2).all()" in route
    assert "DriverTenantSelectionRequired" in route
    assert "DeliveryPerson.tenant_id == self._tenant_id" in service
    assert "func.lower(DeliveryPerson.email)" in service


class _LoginQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_conditions):
        return self

    def limit(self, _limit):
        return self

    def all(self):
        return self.rows

    def first(self):  # pragma: no cover - proves the login lookup never chooses a first row.
        raise AssertionError("login lookup must not call first()")


class _LoginDb:
    def __init__(self, rows):
        self.rows = rows

    def query(self, _model):
        return _LoginQuery(self.rows)


class _Driver:
    def __init__(self, driver_id: str, tenant_id: str):
        self.id = driver_id
        self.tenant_id = tenant_id


def test_driver_login_denies_ambiguous_email_before_password_check() -> None:
    with pytest.raises(DomainError) as exc:
        _driver_login_service(
            _LoginDb([_Driver("driver-a", "tenant-a"), _Driver("driver-b", "tenant-b")]),
            "driver@example.test",
            None,
        )
    assert exc.value.code == "DriverTenantSelectionRequired"


def test_wave7_logistics_fails_closed_and_scopes_runtime_reads() -> None:
    service = SERVICE.read_text(encoding="utf-8")
    route = ROUTE.read_text(encoding="utf-8")

    assert "wave7_orm_enabled" in service
    assert "Contexto confiavel obrigatorio para logistica da Wave 7." in service
    assert "self._scope(self._db.query(Delivery), Delivery)" in service
    assert "self._scope(self._db.query(DeliveryEarning), DeliveryEarning)" in service
    assert "self._scope(self._db.query(LogisticsSettings), LogisticsSettings)" in service
    assert "trusted_process_context(" in route


def test_order_assignment_uses_orders_edit_rbac_and_preserves_post_completion_history() -> None:
    route = ROUTE.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")

    assert 'Depends(require_rbac_permission("pedidos", "edit"))' in route
    assert "OrderStatus.cancelled, OrderStatus.refunded" in service
    assert "previous_status" in service
    assert "previous_delivered_at" in service
    assert "previous_delivery_person_id" in service
    assert "previous_person.status = DeliveryPersonStatus.available" in service
    assert "DeliveryStatus.delivered" in service


class _AssignQuery:
    def __init__(self, delivery):
        self.delivery = delivery

    def filter(self, *_conditions):
        return self

    def first(self):
        return self.delivery


class _AssignDb:
    def __init__(self, delivery):
        self.query_result = _AssignQuery(delivery)
        self.commits = 0

    def query(self, _model):
        return self.query_result

    def commit(self):
        self.commits += 1

    def refresh(self, _entity):
        return None

    def flush(self):
        return None


def _assignment_service(delivery, order, old_person, new_person):
    service = DeliveryService.__new__(DeliveryService)
    service._db = _AssignDb(delivery)
    service._tenant_id = None
    service._tenant_enabled = False
    events = []
    service._add_event = lambda *args, **kwargs: events.append((args, kwargs))
    service._get_order = lambda _order_id: order
    service._get_delivery_person = lambda _person_id: new_person
    service._get_any_delivery_person = lambda _person_id: old_person
    return service, events


def test_terminal_assignment_only_changes_driver_and_preserves_delivery_evidence() -> None:
    delivery = SimpleNamespace(
        id="delivery-terminal",
        order_id="order-terminal",
        delivery_person_id="driver-old",
        status=DeliveryStatus.completed,
        assigned_at="assigned",
        picked_up_at="picked",
        delivered_at="delivered",
        delivery_photo_url="proof.jpg",
        recipient_name="Cliente",
    )
    order = SimpleNamespace(id="order-terminal", status=SimpleNamespace(value="delivered"))
    old = SimpleNamespace(id="driver-old", name="Antigo", status=DeliveryPersonStatus.available)
    new = SimpleNamespace(id="driver-new", name="Novo", status=DeliveryPersonStatus.available)
    service, events = _assignment_service(delivery, order, old, new)

    result = service.assign("order-terminal", "driver-new", estimated_minutes=30)

    assert result is delivery
    assert delivery.delivery_person_id == "driver-new"
    assert delivery.status is DeliveryStatus.completed
    assert delivery.picked_up_at == "picked"
    assert delivery.delivered_at == "delivered"
    assert delivery.delivery_photo_url == "proof.jpg"
    assert delivery.recipient_name == "Cliente"
    assert old.status is DeliveryPersonStatus.available
    assert new.status is DeliveryPersonStatus.available
    assert events[0][1]["metadata"]["previous_delivery_person_id"] == "driver-old"
    assert events[0][1]["metadata"]["previous_status"] == "completed"


def test_active_assignment_keeps_previous_reattribution_behavior() -> None:
    delivery = SimpleNamespace(
        id="delivery-active",
        order_id="order-active",
        delivery_person_id="driver-old",
        status=DeliveryStatus.assigned,
        assigned_at="old-assigned",
        picked_up_at="old-picked",
        delivered_at="old-delivered",
        delivery_photo_url="old-proof.jpg",
        recipient_name="Old",
        estimated_minutes=50,
        confirmation_code="1111",
        confirmed_by_code_at="confirmed",
        tenant_id="tenant-a",
    )
    order = SimpleNamespace(id="order-active", status=SimpleNamespace(value="preparing"))
    old = SimpleNamespace(id="driver-old", name="Antigo", status=DeliveryPersonStatus.busy)
    new = SimpleNamespace(id="driver-new", name="Novo", status=DeliveryPersonStatus.available)
    service, _events = _assignment_service(delivery, order, old, new)

    result = service.assign("order-active", "driver-new", estimated_minutes=30)

    assert result is delivery
    assert delivery.delivery_person_id == "driver-new"
    assert delivery.status is DeliveryStatus.assigned
    assert delivery.picked_up_at is None
    assert delivery.delivered_at is None
    assert delivery.delivery_photo_url is None
    assert delivery.recipient_name is None
    assert old.status is DeliveryPersonStatus.available
    assert new.status is DeliveryPersonStatus.busy
