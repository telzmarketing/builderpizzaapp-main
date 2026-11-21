"""A legacy order debit can cover each first physical unit only once."""
from decimal import Decimal

import pytest

from test_kds_stock_gate import gate  # shared isolated stock fixture
from backend.core.exceptions import DomainError
from backend.models.cmv import OrderItemCmvIngredientSnapshot, OrderItemCmvSnapshot
from backend.models.inventory import InventoryStockMovement
from backend.models.kds_production import ProductionAttempt, ProductionAttemptConsumption, ProductionUnit


def setup_legacy(gate, covered):
    gate.db.get(OrderItemCmvSnapshot, "snapshot1").quantity = 2
    gate.db.get(OrderItemCmvIngredientSnapshot, "ingredient1").quantity = 2
    gate.db.add(InventoryStockMovement(
        id="legacy-sale", tenant_id="tenant", item_id="cheese", location_id="kitchen",
        source_type="order_sale", source_id="order1", quantity_delta=-covered,
    ))
    gate.db.add(ProductionUnit(id="unit1-second", tenant_id="tenant", order_id="order1",
        order_item_id="item1", unit_index=2, state="queued"))
    gate.db.add(ProductionAttempt(id="task1-second", tenant_id="tenant", production_unit_id="unit1-second",
        attempt_number=1, state="queued"))
    gate.db.commit()


def test_legacy_debit_is_attributed_per_unit_without_new_movements(gate):
    setup_legacy(gate, 2)
    for task in ("task1", "task1-second"):
        assert gate.service.consume_attempt(task, "cook", require_stock=True)["reason"] == "legacy_covered"
        gate.db.commit()
    assert gate.db.query(ProductionAttemptConsumption).count() == 2
    assert sum((line.quantity for line in gate.db.query(ProductionAttemptConsumption)), Decimal(0)) == 2
    assert gate.db.query(InventoryStockMovement).count() == 2
    assert gate.service.consume_attempt("task1", "cook", require_stock=True)["reason"] == "already_consumed"


def test_incomplete_legacy_debit_cannot_be_reused_for_another_unit(gate):
    setup_legacy(gate, 1)
    gate.service.consume_attempt("task1", "cook", require_stock=True)
    gate.db.commit()
    with pytest.raises(DomainError) as failure:
        gate.service.consume_attempt("task1-second", "cook", require_stock=True)
    gate.db.rollback()
    assert failure.value.code == "LegacyCoverageIncomplete"
    assert gate.db.query(ProductionAttemptConsumption).count() == 1
    assert gate.db.query(InventoryStockMovement).count() == 2
