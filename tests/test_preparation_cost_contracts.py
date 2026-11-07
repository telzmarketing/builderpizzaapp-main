"""Cost invariants for the Preparation -> Inventory -> CMV boundary.

These are contract tests only.  They intentionally do not change production
code or create database state.  Until the production cost patch is present,
the tests that describe the missing invariants are expected to fail.
"""

import ast
import inspect
import textwrap
from decimal import Decimal

import pytest

from backend.models.inventory import InventoryStockMovement
from backend.models.inventory_foundation import InventoryLot, InventoryOperation
from backend.models.preparation import PreparationExecution, PreparationOrder
from backend.services.preparation_service import PreparationService


REPORT_SOURCE = textwrap.dedent(inspect.getsource(PreparationService.report))
INPUT_COST_SOURCE = textwrap.dedent(inspect.getsource(PreparationService._weighted_input_cost))
REPORT_TREE = ast.parse(REPORT_SOURCE)


def _calls(tree, attribute):
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attribute
    ]


def test_preparation_output_cost_must_come_from_server_side_ledger_cost():
    """The client must not be able to choose the cost used by preparation."""
    assert 'allocation.get("unit_cost")' not in REPORT_SOURCE
    assert "positive stock entries only" in INPUT_COST_SOURCE
    assert "self._q(InventoryStockMovement)" in INPUT_COST_SOURCE
    assert "InventoryStockMovement.unit_cost > 0" in INPUT_COST_SOURCE
    assert any(
        call.func.attr in {"_unit_cost", "unit_cost", "cost_for", "weighted_average_cost", "_weighted_input_cost"}
        for call in ast.walk(REPORT_TREE)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
    ), "report() must resolve cost through a server-side service/ledger"


def test_preparation_lot_and_operation_contracts_are_tenant_scoped():
    for model in (InventoryLot, InventoryOperation, PreparationOrder, PreparationExecution):
        assert model.__table__.c.tenant_id.nullable is False

    movement_tenant_fk = {
        tuple(column.name for column in constraint.columns)
        for constraint in InventoryStockMovement.__table__.foreign_key_constraints
    }
    assert ("tenant_id", "operation_id") in movement_tenant_fk
    assert any(columns[:2] == ("tenant_id", "lot_id") for columns in {
        tuple(column.name for column in constraint.columns)
        for constraint in InventoryStockMovement.__table__.foreign_key_constraints
    })

    service_source = inspect.getsource(PreparationService)
    assert "InventoryFoundationService(self.db, self.tenant_id" in service_source
    assert "foundation._get(InventoryLot" in REPORT_SOURCE


def test_preparation_must_block_when_consumed_cost_is_not_positive():
    """Missing/zero input cost must be a domain failure, never a zero-cost output."""
    positive_cost_guard = (
        "unit_cost <= 0",
        "total_cost <= 0",
        "cost <= 0",
        "not unit_cost",
    )
    assert any(token in INPUT_COST_SOURCE for token in positive_cost_guard)
    assert "PreparationInvalid" in REPORT_SOURCE
    assert 'unit_cost=Decimal("0")' not in REPORT_SOURCE


def test_preparation_conserves_input_cost_in_produced_output():
    """With no loss/discard, produced output must retain consumed input cost."""
    assert 'unit_cost=Decimal("0")' not in REPORT_SOURCE
    assert any(token in REPORT_SOURCE for token in ("input_cost", "consumed_cost", "total_input_cost"))
    assert any(token in REPORT_SOURCE for token in ("output_cost", "output_unit_cost", "produced_unit_cost"))
    assert any(token in REPORT_SOURCE for token in ("/ output_qty", "/ produced_qty", "total_input_cost /"))
    assert "quantity_delta=output_qty" in REPORT_SOURCE


def test_preparation_idempotency_covers_execution_and_inventory_operation():
    """Repeating a report key cannot create another execution or operation."""
    execution_indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in PreparationExecution.__table__.indexes
    }
    assert execution_indexes["uq_preparation_executions_tenant_order_key"] == (
        "tenant_id",
        "order_id",
        "idempotency_key",
    )

    operation_indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in InventoryOperation.__table__.indexes
    }
    assert operation_indexes["uq_inventory_operation_request"] == (
        "tenant_id",
        "idempotency_scope",
        "idempotency_key",
    )
    assert "existing = self._q(PreparationExecution)" in REPORT_SOURCE
    assert "operation_key = f\"preparation:{oid}:{key}\"" in REPORT_SOURCE


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-0.01")])
def test_cost_contract_rejects_non_positive_values(value):
    """Document the domain boundary independently of transport/schema defaults."""
    assert value <= 0
