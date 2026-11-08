from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.models.inventory import InventoryItem
from backend.models.inventory_portion import InventoryPortionConfig
from backend.services.inventory_foundation_service import FoundationInvalid
from backend.services.recipe_supply_resolver import RecipeSupplyResolver


class _Query:
    def __init__(self, value):
        self.value = value

    def filter(self, *_args, **_kwargs):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.value


class _Db:
    def __init__(self, config, item):
        self.config = config
        self.item = item

    def query(self, model):
        if model is InventoryPortionConfig:
            return _Query(self.config)
        if model is InventoryItem:
            return _Query(self.item)
        raise AssertionError(model)


def _values():
    return {
        "supply_mode": "portion",
        "portion_config_id": "portion-1",
        "portion_config_version": 1,
        "quantity": Decimal("1"),
        "unit_id": "unit-g",
    }


def test_portion_source_must_match_recipe_size():
    config = SimpleNamespace(id="portion-1", active=True, version=1, size="Grande", output_item_id="output-1")
    item = SimpleNamespace(id="output-1", active=True, unit_id="unit-g")
    resolver = RecipeSupplyResolver(_Db(config, item), "tenant-a")

    with pytest.raises(FoundationInvalid, match="tamanho da ficha"):
        resolver.resolve_line(_values(), recipe_size_label="Broto")

    resolved = resolver.resolve_line(_values(), recipe_size_label=" grande ")
    assert resolved["inventory_item_id"] == "output-1"
    assert resolved["portion_config_version"] == 1


def test_sized_portion_can_be_selected_by_generic_recipe():
    config = SimpleNamespace(id="portion-1", active=True, version=1, size="Grande", output_item_id="output-1")
    item = SimpleNamespace(id="output-1", active=True, unit_id="unit-g")
    resolved = RecipeSupplyResolver(_Db(config, item), "tenant-a").resolve_line(_values())
    assert resolved["inventory_item_id"] == "output-1"
    assert resolved["supply_mode"] == "portion"


def test_global_portion_source_can_be_used_by_a_sized_recipe():
    config = SimpleNamespace(id="portion-1", active=True, version=1, size=None, output_item_id="output-1")
    item = SimpleNamespace(id="output-1", active=True, unit_id="unit-g")
    resolved = RecipeSupplyResolver(_Db(config, item), "tenant-a").resolve_line(
        _values(), recipe_size_label="Grande"
    )
    assert resolved["supply_mode"] == "portion"
