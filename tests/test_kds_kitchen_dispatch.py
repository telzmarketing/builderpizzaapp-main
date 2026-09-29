from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.core.kds_station_access import station_path_allowed
from backend.core.state_machine import order_sm
from backend.core.tenant_context import TenantContext, TenantSource
from backend.main import app
from backend.models.delivery import DeliveryStatus
from backend.models.order import Order, OrderStatus
from backend.schemas.kds import DispatchAssignIn
from backend.services.kds_service import KdsService


ROOT = Path(__file__).resolve().parents[1]


def test_station_accounts_are_fail_closed_outside_their_kds_surface():
    assert station_path_allowed("cozinha", "/api/kds/kitchen/orders")
    assert not station_path_allowed("cozinha", "/api/orders")
    assert not station_path_allowed("cozinha", "/api/kds/dispatch/orders")
    assert station_path_allowed("expedicao", "/api/kds/dispatch/drivers")
    assert not station_path_allowed("expedicao", "/api/delivery/active")
    assert station_path_allowed("expedicao", "/api/admin/auth/me/permissions")


def test_dispatch_payload_is_bounded_and_uses_delivery_person_contract():
    assert DispatchAssignIn(delivery_person_id="driver-1").estimated_minutes == 40
    with pytest.raises(ValidationError):
        DispatchAssignIn(delivery_person_id="driver-1", estimated_minutes=0)
    with pytest.raises(ValidationError):
        DispatchAssignIn(delivery_person_id="", estimated_minutes=40)


def test_kds_routes_are_registered_under_api_prefix():
    paths = {route.path for route in app.routes}
    assert "/api/kds/kitchen/orders" in paths
    assert "/api/kds/kitchen/orders/{order_id}/start" in paths
    assert "/api/kds/kitchen/orders/{order_id}/ready" in paths
    assert "/api/kds/kitchen/orders/{order_id}/pickup-complete" in paths
    assert "/api/kds/dispatch/orders" in paths
    assert "/api/kds/dispatch/drivers" in paths
    assert "/api/kds/dispatch/orders/{order_id}/pickup-complete" in paths
    assert "/api/kds/dispatch/orders/{order_id}/assign" in paths


def test_kds_service_accepts_a_trusted_legacy_job_context():
    context = TenantContext(tenant_id="tenant-legacy-default", source=TenantSource.JOB)
    service = KdsService(object(), context)
    assert service.tenant_id == "tenant-legacy-default"
    assert service.tenant_context is context


def test_order_model_has_fulfillment_constraint_and_no_implicit_server_default():
    checks = {constraint.name for constraint in Order.__table__.constraints}
    assert "ck_orders_fulfillment_type" in checks
    assert Order.__table__.c.fulfillment_type.server_default is None


def test_migration_is_based_on_current_head_and_removes_temporary_default():
    source = (ROOT / "backend/migrations/versions/20260924_kds_kitchen_dispatch.py").read_text(encoding="utf-8")
    assert 'down_revision = "20260923_pagarme_tenant_gateway"' in source
    assert "ck_orders_fulfillment_type" in source
    assert "server_default=None" in source
    assert "lower(trim(coalesce(delivery_street, ''))) = 'retirada no local'" in source


def test_dispatch_assignment_does_not_advance_order_to_on_the_way_in_service_source():
    source = (ROOT / "backend/services/kds_service.py").read_text(encoding="utf-8")
    assignment = source[source.index("    def assign_driver("):source.index("    def _audit_order_transition(")]
    assert "order.status = OrderStatus.on_the_way" not in assignment
    assert "DeliveryStatus.assigned" in assignment
    assert "DeliveryPersonStatus.available" in assignment
    assert ".with_for_update()" in assignment


def test_delivery_flow_cannot_skip_route_but_pickup_has_a_dedicated_operation():
    assert not order_sm.can_transition("ready_for_pickup", "delivered")
    source = (ROOT / "backend/services/order_service.py").read_text(encoding="utf-8")
    assert "def complete_customer_pickup(" in source
    assert 'order.fulfillment_type != "pickup"' in source


def test_kitchen_mutations_reuse_authoritative_order_service():
    source = (ROOT / "backend/services/kds_service.py").read_text(encoding="utf-8")
    assert source.count("OrderService(") >= 3
    assert ".change_status(" in source
    assert ".complete_customer_pickup(" in source
    assert "with_for_update(of=Order)" in source


def test_kds_payload_does_not_expose_customer_phone():
    source = (ROOT / "backend/services/kds_service.py").read_text(encoding="utf-8")
    assert '"delivery_phone"' not in source


def test_ready_pickup_moves_from_kitchen_to_dispatch_and_uses_dispatch_audit():
    source = (ROOT / "backend/services/kds_service.py").read_text(encoding="utf-8")
    kitchen = source[source.index("    def kitchen_orders("):source.index("    def start_preparation(")]
    dispatch = source[source.index("    def dispatch_orders("):source.index("    def available_drivers(")]
    routes = (ROOT / "backend/routes/kds.py").read_text(encoding="utf-8")

    assert "OrderStatus.ready_for_pickup" not in kitchen
    assert 'Order.fulfillment_type == "pickup"' in dispatch
    assert '@router.post("/dispatch/orders/{order_id}/pickup-complete")' in routes
    assert 'require_rbac_permission("expedicao", "edit")' in routes
    assert 'audit_module="expedicao"' in routes


def test_kitchen_eager_loads_and_exposes_only_bounded_delivery_identity():
    source = (ROOT / "backend/services/kds_service.py").read_text(encoding="utf-8")
    kitchen = source[source.index("    def kitchen_orders("):source.index("    def start_preparation(")]
    assert "joinedload(Order.delivery).joinedload(Delivery.delivery_person)" in kitchen

    assigned_at = datetime(2026, 9, 27, 19, 0, tzinfo=timezone.utc)
    driver = SimpleNamespace(id="driver-1", name="Carlos Silva")
    delivery = SimpleNamespace(
        id="delivery-1", status=DeliveryStatus.assigned,
        delivery_person_id=driver.id, delivery_person=driver,
        assigned_at=assigned_at,
    )
    order = SimpleNamespace(
        id="order-1", order_code="1043", status=OrderStatus.preparing,
        fulfillment_type="delivery", sales_channel="delivery", notes=None,
        total=79.9, estimated_time=40,
        created_at=assigned_at, updated_at=assigned_at,
        preparation_started_at=assigned_at, items=[], payment=SimpleNamespace(
            method="cash", pay_on_delivery=True, delivery_payment_method="cash",
            cash_needs_change=True, cash_change_for=100,
        ), delivery=delivery,
        delivery_name="Cliente", delivery_street="Rua privada",
        delivery_city="Cidade", delivery_complement="Apto 1",
    )
    context = TenantContext(tenant_id="tenant-a", source=TenantSource.JOB)
    payload = KdsService(SimpleNamespace(), context)._serialize_orders(
        [order], include_dispatch_details=False,
    )[0]

    assert payload["delivery"] == {
        "id": "delivery-1", "status": "assigned",
        "delivery_person_id": "driver-1",
        "delivery_person_name": "Carlos Silva",
        "assigned_at": assigned_at,
    }
    assert set(payload).isdisjoint({
        "delivery_name", "delivery_street", "delivery_city",
        "delivery_complement", "payment_method", "pay_on_delivery",
        "delivery_payment_method", "cash_needs_change", "cash_change_for",
        "can_assign_driver",
    })


def test_dispatch_keeps_assigned_order_visible_but_marks_it_read_only():
    assert DeliveryStatus.assigned not in KdsService.DISPATCH_HIDDEN_DELIVERY_STATUSES
    assert DeliveryStatus.picked_up in KdsService.DISPATCH_HIDDEN_DELIVERY_STATUSES
    assert DeliveryStatus.on_the_way in KdsService.DISPATCH_HIDDEN_DELIVERY_STATUSES

    now = datetime(2026, 9, 27, 19, 0, tzinfo=timezone.utc)
    driver = SimpleNamespace(id="driver-1", name="Carlos Silva")
    base = dict(
        id="order-1", order_code="1043", status=OrderStatus.ready_for_pickup,
        fulfillment_type="delivery", sales_channel="delivery", notes=None,
        total=79.9, estimated_time=40, created_at=now, updated_at=now,
        preparation_started_at=now, items=[], payment=None,
        delivery_name="Cliente", delivery_street="Rua A", delivery_city="Cidade",
        delivery_complement=None,
    )
    context = TenantContext(tenant_id="tenant-a", source=TenantSource.JOB)
    service = KdsService(SimpleNamespace(), context)

    assigned = SimpleNamespace(
        id="delivery-1", status=DeliveryStatus.assigned,
        delivery_person_id=driver.id, delivery_person=driver, assigned_at=now,
    )
    assigned_payload = service._serialize_orders(
        [SimpleNamespace(**base, delivery=assigned)], include_dispatch_details=True,
    )[0]
    assert assigned_payload["delivery"]["delivery_person_name"] == "Carlos Silva"
    assert assigned_payload["can_assign_driver"] is False

    failed = SimpleNamespace(
        id="delivery-2", status=DeliveryStatus.failed,
        delivery_person_id=None, delivery_person=None, assigned_at=None,
    )
    failed_payload = service._serialize_orders(
        [SimpleNamespace(**base, delivery=failed)], include_dispatch_details=True,
    )[0]
    assert failed_payload["can_assign_driver"] is True


def test_status_change_does_not_auto_assign_before_dispatch_release():
    main_source = (ROOT / "backend/main.py").read_text(encoding="utf-8")
    delivery_source = (ROOT / "backend/services/delivery_service.py").read_text(encoding="utf-8")
    auto_assign = delivery_source[
        delivery_source.index("    def auto_assign_pending("):
        delivery_source.index("    def geocode_address(")
    ]

    assert "_auto_assign_handler" not in main_source
    assert "bus.subscribe(OrderStatusChanged, _auto_assign_handler)" not in main_source
    assert "def auto_assign_pending(self)" in auto_assign
    assert "DispatchReleaseRequired" not in auto_assign
