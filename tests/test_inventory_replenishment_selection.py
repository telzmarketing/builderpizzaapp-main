from types import SimpleNamespace
from importlib import import_module
from pkgutil import iter_modules

import pytest
from pydantic import ValidationError

# Load the complete model registry before constructing InventoryPurchase. This
# mirrors the project test setup and resolves cross-module foreign keys.
import backend.models

for module in iter_modules(backend.models.__path__):
    import_module(f"backend.models.{module.name}")

from backend.models.inventory import InventoryItem, InventoryPurchaseItem
from backend.schemas.inventory import InventoryReplenishmentRequestIn
from backend.services.inventory_service import InventoryInvalidReference, InventoryNotFound, InventoryService


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class _Db:
    def __init__(self, items):
        self.items = items
        self.added = []

    def query(self, model):
        return _Query(self.items if model is InventoryItem else [])

    def add(self, row):
        self.added.append(row)

    def commit(self):
        return None

    def refresh(self, _row):
        return None


def _service(db, items):
    service = InventoryService(db, "tenant-a", actor_id="admin-a")
    service._stock_balance_map = lambda: {item.id: 0 for item in items}
    service._ensure = lambda _model, item_id, _label: next(item for item in items if item.id == item_id)
    service._serialize_purchase = lambda purchase: {
        "id": purchase.id,
        "items": [row.item_id for row in db.added if isinstance(row, InventoryPurchaseItem)],
    }
    return service


def test_replenishment_accepts_selected_tenant_items_and_keeps_calculation():
    items = [
        SimpleNamespace(id="item-a", tenant_id="tenant-a", name="A", active=True, item_type="ingredient", min_stock=5),
        SimpleNamespace(id="item-b", tenant_id="tenant-a", name="B", active=True, item_type="ingredient", min_stock=3),
        SimpleNamespace(id="finished", tenant_id="tenant-a", name="Finished", active=True, item_type="finished_good", min_stock=10),
    ]
    db = _Db(items)

    result = _service(db, items).create_replenishment_request(["item-b"])

    assert result["items"] == ["item-b"]
    purchase_item = next(row for row in db.added if isinstance(row, InventoryPurchaseItem))
    assert purchase_item.quantity == 3
    assert purchase_item.unit_cost == 0


def test_replenishment_without_body_keeps_all_below_minimum_compatibility():
    items = [
        SimpleNamespace(id="item-a", tenant_id="tenant-a", name="A", active=True, item_type="ingredient", min_stock=5),
        SimpleNamespace(id="item-b", tenant_id="tenant-a", name="B", active=True, item_type="ingredient", min_stock=3),
    ]
    db = _Db(items)

    result = _service(db, items).create_replenishment_request()

    assert result["items"] == ["item-a", "item-b"]


def test_replenishment_rejects_item_from_another_tenant():
    items = [SimpleNamespace(id="item-a", tenant_id="tenant-a", name="A", active=True, item_type="ingredient", min_stock=5)]
    db = _Db(items)

    with pytest.raises(InventoryNotFound):
        _service(db, items).create_replenishment_request(["foreign-item"])


def test_replenishment_rejects_selected_item_above_minimum():
    items = [SimpleNamespace(id="item-a", tenant_id="tenant-a", name="A", active=True, item_type="ingredient", min_stock=5)]
    db = _Db(items)
    service = _service(db, items)
    service._stock_balance_map = lambda: {"item-a": 5}

    with pytest.raises(InventoryInvalidReference):
        service.create_replenishment_request(["item-a"])


def test_replenishment_schema_rejects_empty_selection():
    with pytest.raises(ValidationError):
        InventoryReplenishmentRequestIn(item_ids=[])
