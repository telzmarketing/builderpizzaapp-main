import inspect
from types import SimpleNamespace
from decimal import Decimal

import pytest

from backend.core.exceptions import DomainError
from backend.routes import preparation as preparation_routes
from backend.services.preparation_service import PreparationNotFound, PreparationService


def test_get_order_uses_the_official_projection_and_tenant_scoped_lookup():
    service = PreparationService(db=None, tenant_id="tenant-a", actor_id="admin-a")
    order = SimpleNamespace(id="order-a")
    service._order = lambda order_id: order
    service._out = lambda value: {"id": value.id, "status": "draft"}

    assert service.get_order("order-a") == {"id": "order-a", "status": "draft"}


def test_get_order_preserves_not_found_for_another_tenant():
    service = PreparationService(db=None, tenant_id="tenant-a", actor_id="admin-a")

    def missing(_order_id):
        raise PreparationNotFound("Ordem nao encontrada neste tenant.")

    service._order = missing

    with pytest.raises(PreparationNotFound):
        service.get_order("order-from-tenant-b")


def test_get_order_route_is_read_only_and_uses_view_permission():
    route = next(
        route for route in preparation_routes.router.routes
        if getattr(route, "path", None) == "/preparation/orders/{order_id}"
    )
    assert "GET" in route.methods
    assert route.response_model.__name__ == "PreparationOrderOut"
    assert "get_order" in inspect.getsource(route.endpoint)
    assert any(dependency.call is preparation_routes.view for dependency in route.dependant.dependencies)


def test_preparation_output_cost_is_server_calculated_and_audited():
    source = inspect.getsource(PreparationService.report)
    assert "self._weighted_input_cost(item_id, lot_id)" in source
    assert 'unit_cost=unit_cost' in source
    assert 'unit_cost=Decimal(str(allocation.get("unit_cost") or 0))' not in source
    assert '"input_cost_total"' in source
    assert '"output_cost_total"' in source
    assert '"output_unit_cost"' in source
    assert '"allocations"' in source


def test_weighted_input_cost_is_tenant_scoped_and_optionally_lot_scoped():
    source = inspect.getsource(PreparationService._weighted_input_cost)
    assert "self._q(InventoryStockMovement)" in source
    assert "quantity_delta > 0" in source
    assert "unit_cost > 0" in source
    assert "InventoryStockMovement.lot_id == lot_id" in source
    assert "total_cost / quantity" in source


def test_preparation_cost_failure_is_a_domain_error():
    source = inspect.getsource(PreparationService._weighted_input_cost)
    assert "raise PreparationInvalid" in source
    assert "Custo positivo insuficiente" in source


class _RowsQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def with_for_update(self):
        return self

    def all(self):
        return self.rows


def test_weighted_cost_conserves_input_cost_in_output_cost():
    rows = [
        SimpleNamespace(quantity_delta=Decimal("4"), unit_cost=Decimal("10")),
        SimpleNamespace(quantity_delta=Decimal("6"), unit_cost=Decimal("20")),
    ]
    service = PreparationService(db=None, tenant_id="tenant-a", actor_id="admin-a")
    service._q = lambda _model: _RowsQuery(rows)

    quantity, total, unit_cost = service._weighted_input_cost("item-a")
    produced = Decimal("5")
    output_unit_cost = total / produced

    assert quantity == Decimal("10")
    assert total == Decimal("160")
    assert unit_cost == Decimal("16")
    assert produced * output_unit_cost == total


def test_weighted_cost_blocks_when_no_positive_cost_exists():
    service = PreparationService(db=None, tenant_id="tenant-a", actor_id="admin-a")
    service._q = lambda _model: _RowsQuery([
        SimpleNamespace(quantity_delta=Decimal("10"), unit_cost=Decimal("0")),
    ])

    with pytest.raises(DomainError, match="Custo positivo insuficiente"):
        service._weighted_input_cost("item-a")


def test_report_repetition_returns_existing_execution_before_version_validation():
    service = PreparationService(db=None, tenant_id="tenant-a", actor_id="admin-a")
    order = SimpleNamespace(id="order-a", version=9, status="completed")
    execution = SimpleNamespace(id="execution-a")
    service._order = lambda _order_id, _lock=False: order
    service._q = lambda _model: SimpleNamespace(
        filter_by=lambda **_filters: SimpleNamespace(first=lambda: execution)
    )
    service._out = lambda _order, execution_id=None: {
        "id": _order.id,
        "execution_id": execution_id,
    }

    result = service.report(
        "order-a",
        SimpleNamespace(expected_version=1),
        "same-request",
    )

    assert result == {"id": "order-a", "execution_id": "execution-a"}
