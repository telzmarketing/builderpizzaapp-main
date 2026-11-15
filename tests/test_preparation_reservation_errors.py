from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.core.exceptions import DomainError
from backend.models.inventory import InventoryItem, InventoryLocation, InventoryUnit
from backend.services import preparation_service
from backend.services.preparation_service import PreparationService


class _Query:
    def filter(self, *args):
        return self

    def first(self):
        return None


class _Foundation:
    def __init__(self, item, unit, location, available):
        self.item = item
        self.unit = unit
        self.location = location
        self.available = available

    def _lock_items(self, item_ids):
        return [self.item]

    def _get(self, model, resource_id, lock=False):
        if model is InventoryUnit:
            return self.unit
        if model is InventoryLocation:
            return self.location
        raise AssertionError(f"unexpected model lookup: {model}")

    def _available(self, item_id, location_id, lot_id):
        return self.available


def test_reservation_conflict_explains_required_free_stock_and_default_location(monkeypatch):
    item = SimpleNamespace(
        id="item-broccoli",
        name="Brócolis",
        unit_id="unit-cbc",
        default_location_id="location-freezer",
    )
    unit = SimpleNamespace(id="unit-cbc")
    location = SimpleNamespace(id="location-freezer", name="Freezer de Conservas")
    foundation = _Foundation(item, unit, location, Decimal("5"))
    monkeypatch.setattr(preparation_service, "InventoryFoundationService", lambda *args: foundation)

    service = PreparationService(db=None, tenant_id="tenant-a", actor_id="admin-a")
    service._q = lambda _model: _Query()
    service._to_item_base_quantity = lambda item, unit, quantity, foundation: (item.unit_id, quantity)
    order = SimpleNamespace(id="order-1", target_quantity=Decimal("10"))
    recipe = SimpleNamespace(
        yield_quantity=Decimal("10"),
        items=[SimpleNamespace(item_id=item.id, unit_id=unit.id, quantity=Decimal("10"))],
    )

    with pytest.raises(DomainError) as error:
        service._reserve_order_inputs(order, recipe)

    message = str(error.value)
    assert message.startswith("Saldo insuficiente para reservar o insumo")
    assert "Brócolis (item-broccoli)" in message
    assert "quantidade necessaria 10" in message
    assert "saldo livre 5" in message
    assert "local padrao Freezer de Conservas (location-freezer)" in message
