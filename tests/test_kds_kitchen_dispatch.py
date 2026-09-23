from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.core.kds_station_access import station_path_allowed
from backend.core.state_machine import order_sm
from backend.core.tenant_context import TenantContext, TenantSource
from backend.main import app
from backend.models.order import Order
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
