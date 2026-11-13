"""Operational contracts for the Print Pedido integration.

These tests intentionally do not require a live PostgreSQL database.  The
source contracts protect the ownership boundaries, while the small inventory
tests exercise the fail-closed gates without creating stock movements.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import SimpleNamespace

from backend.models.kds_production import ProductionUnit
from backend.models.order import Order
from backend.services.inventory_service import InventoryService
from backend.services.kds_service import KdsService
from backend.services.order_service import OrderService
from backend.services.print_order_service import PrintOrderService


def _method_tree(method) -> ast.FunctionDef:
    return ast.parse(textwrap.dedent(inspect.getsource(method))).body[0]


def _call_with_attribute(tree: ast.AST, attribute: str) -> ast.Call:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == attribute
        ):
            return node
    raise AssertionError(f"call to {attribute} not found")


def test_print_order_confirmation_uses_canonical_order_and_pending_manual_payment():
    tree = _method_tree(PrintOrderService.confirm)
    call = _call_with_attribute(tree, "create_from_checkout")
    keywords = {keyword.arg: keyword.value for keyword in call.keywords}

    assert isinstance(call.func.value, ast.Call)
    assert isinstance(call.func.value.func, ast.Name)
    assert call.func.value.func.id == "OrderService"
    assert isinstance(keywords["order_origin"], ast.Attribute)
    assert keywords["order_origin"].value.id == "row"
    assert keywords["order_origin"].attr == "platform"
    assert isinstance(keywords["payment_status"], ast.Constant)
    assert keywords["payment_status"].value == "pending"
    assert isinstance(keywords["payment_source"], ast.Constant)
    assert keywords["payment_source"].value == "manual"


def test_order_service_owns_cmv_snapshot_creation_for_checkout_orders():
    order_source = inspect.getsource(OrderService.create_from_checkout)
    print_source = inspect.getsource(PrintOrderService.confirm)

    assert "OrderCmvSnapshotService" in order_source
    assert ".create_for_order(order, cmv_contexts)" in order_source
    assert "OrderCmvSnapshotService" not in print_source
    assert "create_for_order" not in print_source


def test_kds_initialization_is_gated_by_approved_status_and_start_preparation():
    kds_tree = _method_tree(KdsService.start_preparation)
    kds_source = inspect.getsource(KdsService.start_preparation)
    print_source = inspect.getsource(PrintOrderService.confirm)

    assert "OrderStatus.paid.value" in kds_source
    assert "OrderStatus.pago.value" in kds_source
    assert "KdsProductionService" in kds_source
    assert "initialize_order(order_id, actor_id, commit=False)" in kds_source
    assert "start_preparation" not in print_source
    assert "initialize_order" not in print_source

    # Keep the contract explicit: the approved-state guard is in the method
    # that owns KDS initialization, before the initialization call.
    guard = next(
        node
        for node in ast.walk(kds_tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and any(isinstance(op, ast.NotIn) for op in node.test.ops)
    )
    initialize_line = next(
        node.lineno
        for node in ast.walk(kds_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "initialize_order"
    )
    assert guard.lineno < initialize_line


class _Query:
    def __init__(self, result):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        return self

    def with_for_update(self, **kwargs):
        return self

    def first(self):
        return self.result


class _InventoryGateDb:
    def __init__(self, order, production_unit=None):
        self.order_query = _Query(order)
        self.production_query = _Query(production_unit)
        self.production_queries = 0

    def query(self, model):
        if model is Order:
            return self.order_query
        if getattr(model, "class_", None) is ProductionUnit:
            self.production_queries += 1
            return self.production_query
        raise AssertionError(f"unexpected inventory query: {model!r}")


def _inventory_service(db):
    service = InventoryService(db, "tenant-print-order")
    service.automatic_deduction_enabled = lambda: True
    return service


def test_inventory_sale_does_not_consume_before_preparing():
    db = _InventoryGateDb(SimpleNamespace(id="order-1", tenant_id="tenant-print-order", status="paid"))

    result = _inventory_service(db).consume_order_sale("order-1")

    assert result == {"deducted": False, "reason": "not_preparing", "movements": 0}
    assert db.production_queries == 0


def test_inventory_sale_does_not_consume_when_kds_units_exist():
    db = _InventoryGateDb(
        SimpleNamespace(id="order-1", tenant_id="tenant-print-order", status="preparing"),
        production_unit=SimpleNamespace(id="unit-1"),
    )

    result = _inventory_service(db).consume_order_sale("order-1")

    assert result == {"deducted": False, "reason": "kds_units", "movements": 0}
    assert db.production_queries == 1
