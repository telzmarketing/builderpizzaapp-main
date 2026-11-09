from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.models.inventory import InventoryItem, InventoryLocation, InventoryUnit
from backend.models.inventory_foundation import InventoryLot
from backend.services.preparation_service import PreparationInvalid, PreparationService


class _Foundation:
    def __init__(self, rows):
        self.rows = rows

    def _get(self, model, value, lock=False):
        return self.rows[(model, value)]


def _service_and_recipe():
    service = PreparationService(db=None, tenant_id="tenant-a", actor_id="admin-a")
    recipe = SimpleNamespace(
        yield_quantity=Decimal("10"),
        items=[SimpleNamespace(item_id="flour", unit_id="kg", quantity=Decimal("4"))],
    )
    foundation = _Foundation({
        (InventoryItem, "flour"): SimpleNamespace(id="flour"),
        (InventoryUnit, "kg"): SimpleNamespace(id="kg"),
        (InventoryLocation, "kitchen"): SimpleNamespace(id="kitchen"),
        (InventoryLot, "lot-1"): SimpleNamespace(id="lot-1", item_id="flour", location_id="kitchen"),
        (InventoryLot, "lot-2"): SimpleNamespace(id="lot-2", item_id="flour", location_id="kitchen"),
    })
    return service, recipe, foundation


def test_rejects_item_or_unit_not_declared_by_recipe():
    service, recipe, foundation = _service_and_recipe()

    with pytest.raises(PreparationInvalid, match="nao pertencem a receita"):
        service._validate_input_allocations(
            recipe,
            [{"item_id": "sugar", "unit_id": "kg", "quantity": "2", "location_id": "kitchen"}],
            Decimal("5"),
            foundation,
        )

    with pytest.raises(PreparationInvalid, match="nao pertencem a receita"):
        service._validate_input_allocations(
            recipe,
            [{"item_id": "flour", "unit_id": "g", "quantity": "2", "location_id": "kitchen"}],
            Decimal("5"),
            foundation,
        )


def test_rejects_quantity_above_recipe_scaled_quantity():
    service, recipe, foundation = _service_and_recipe()

    with pytest.raises(PreparationInvalid, match="nao respeita a receita"):
        service._validate_input_allocations(
            recipe,
            [{"item_id": "flour", "unit_id": "kg", "quantity": "2.01", "location_id": "kitchen"}],
            Decimal("5"),
            foundation,
        )


def test_rejects_lot_from_another_item_or_location():
    service, recipe, foundation = _service_and_recipe()
    foundation.rows[(InventoryLot, "wrong-item")] = SimpleNamespace(
        id="wrong-item", item_id="sugar", location_id="kitchen"
    )
    foundation.rows[(InventoryLot, "wrong-location")] = SimpleNamespace(
        id="wrong-location", item_id="flour", location_id="warehouse"
    )

    base = {"item_id": "flour", "unit_id": "kg", "quantity": "2", "location_id": "kitchen"}
    with pytest.raises(PreparationInvalid, match="nao pertence ao item"):
        service._validate_input_allocations(recipe, [base | {"lot_id": "wrong-item"}], Decimal("5"), foundation)

    with pytest.raises(PreparationInvalid, match="nao pertence ao local"):
        service._validate_input_allocations(recipe, [base | {"lot_id": "wrong-location"}], Decimal("5"), foundation)


def test_allows_split_lots_when_the_recipe_quantity_is_exact():
    service, recipe, foundation = _service_and_recipe()

    service._validate_input_allocations(
        recipe,
        [
            {"item_id": "flour", "unit_id": "kg", "quantity": "1", "location_id": "kitchen", "lot_id": "lot-1"},
            {"item_id": "flour", "unit_id": "kg", "quantity": "1", "location_id": "kitchen", "lot_id": "lot-2"},
        ],
        Decimal("5"),
        foundation,
    )


def test_converts_portion_unit_to_stock_base_unit():
    service = PreparationService(db=None, tenant_id="tenant-a", actor_id="admin-a")
    recipe = SimpleNamespace(
        yield_quantity=Decimal("1"),
        items=[SimpleNamespace(item_id="calabresa", unit_id="g", quantity=Decimal("150"))],
    )
    allocation = {"item_id": "calabresa", "unit_id": "g", "quantity": "150", "location_id": "kitchen"}
    foundation = _Foundation({
        (InventoryItem, "calabresa"): SimpleNamespace(id="calabresa", unit_id="kg"),
        (InventoryUnit, "g"): SimpleNamespace(id="g", dimension="mass", conversion_factor=Decimal("1")),
        (InventoryUnit, "kg"): SimpleNamespace(id="kg", dimension="mass", conversion_factor=Decimal("1000")),
        (InventoryLocation, "kitchen"): SimpleNamespace(id="kitchen"),
    })

    service._validate_input_allocations(recipe, [allocation], Decimal("1"), foundation)

    assert allocation["unit_id"] == "kg"
    assert allocation["quantity"] == "0.150000"


def test_rejects_malformed_quantity_as_domain_error():
    service, recipe, foundation = _service_and_recipe()

    with pytest.raises(PreparationInvalid, match="Quantidade de consumo invalida"):
        service._validate_input_allocations(
            recipe,
            [{"item_id": "flour", "unit_id": "kg", "quantity": "not-a-number", "location_id": "kitchen"}],
            Decimal("5"),
            foundation,
        )


def test_report_invokes_allocation_validation_before_inventory_mutation():
    import inspect

    from backend.services.preparation_service import PreparationService

    source = inspect.getsource(PreparationService.report)
    assert "self._validate_input_allocations(recipe, b.input_allocations, processed_quantity, foundation)" in source
