from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.services.inventory_portion_conversion import PortionConversionError, source_quantity_for_portion
from backend.services.inventory_portion_service import InventoryPortionConfigService
from backend.services.inventory_service import InventoryInvalidReference, InventoryService


def unit(id, name, dimension, factor):
    return SimpleNamespace(id=id, name=name, symbol=id.upper(), dimension=dimension, conversion_factor=factor, active=True, has_weight=False)


GRAM = unit("g", "Gramas", "mass", Decimal("0.001"))
KILOGRAM = unit("kg", "Quilogramas", "mass", Decimal("1"))


def item(unit_id="kg", weight_quantity=None, weight_unit_id=None):
    return SimpleNamespace(name="Calabresa", unit_id=unit_id, weight_quantity=weight_quantity, weight_unit_id=weight_unit_id)


def test_portion_gr_to_purchased_kg_and_yield():
    assert source_quantity_for_portion(item(), KILOGRAM, GRAM, Decimal("150")) == Decimal("0.150000")
    assert source_quantity_for_portion(item(), KILOGRAM, GRAM, Decimal("150"), Decimal("75")) == Decimal("0.200000")


def test_portion_gr_to_fixed_weight_package():
    package = unit("bucket", "Balde", "count", Decimal("1"))
    source = item("bucket", Decimal("5"), "kg")
    assert source_quantity_for_portion(source, package, GRAM, Decimal("150"), weight_unit=KILOGRAM) == Decimal("0.030000")
    assert source_quantity_for_portion(source, package, GRAM, Decimal("150"), Decimal("75"), KILOGRAM) == Decimal("0.040000")


@pytest.mark.parametrize("source_unit,source,expected", [
    (unit("legacy", "Quilogramas", None, None), item("legacy"), "Classifique a unidade de compra"),
    (unit("bucket", "Balde", "count", Decimal("1")), item("bucket"), "Cadastre o peso total"),
    (unit("l", "Litros", "volume", Decimal("1")), item("l"), "densidade"),
])
def test_incompatible_or_unclassified_units_fail_explicitly(source_unit, source, expected):
    with pytest.raises(PortionConversionError, match=expected):
        source_quantity_for_portion(source, source_unit, GRAM, Decimal("150"))


def test_portion_weight_unit_must_be_mass():
    with pytest.raises(PortionConversionError, match="Classifique a unidade da porcao"):
        source_quantity_for_portion(item(), KILOGRAM, unit("portion", "Porcao", "count", 1), Decimal("150"))


def test_replenishment_estimate_uses_purchased_unit_and_same_conversion_as_recipe(monkeypatch):
    source = item()
    source.id = "raw"
    source.name = "Calabresa"
    row = SimpleNamespace(
        id="config", output_item_id="portioned", output_item=SimpleNamespace(unit_id="count"), unit_id="g", source_item=source, unit=GRAM,
        portion_weight=Decimal("150"), yield_percent=Decimal("100"),
        min_stock=Decimal("30"), target_stock=Decimal("100"), usage="mandatory", size=None,
    )
    service = InventoryPortionConfigService(object(), "tenant", "actor")
    monkeypatch.setattr(service, "list", lambda active=None: [row])
    monkeypatch.setattr(service, "balances", lambda: [{
        "config_id": "config", "available_stock": Decimal("0"), "in_preparation": Decimal("0"),
    }])
    monkeypatch.setattr(service, "_find_unit", lambda unit_id: KILOGRAM if unit_id == "kg" else None)

    alert = service.replenishment_alerts()[0]
    assert alert["suggested_portions"] == Decimal("100")
    assert alert["estimated_source_quantity"] == Decimal("15.000000")
    assert alert["source_unit_symbol"] == "KG"
    assert alert["conversion_error"] is None


def test_fixed_package_weight_can_be_registered_for_count_unit_even_without_has_weight_flag(monkeypatch):
    service = object.__new__(InventoryService)
    package = unit("bucket", "Balde", "count", Decimal("1"))
    package.has_weight = False
    monkeypatch.setattr(service, "_ensure", lambda model, id, label: {"bucket": package, "kg": KILOGRAM}[id])
    service._validate_item_refs({"unit_id": "bucket", "weight_quantity": Decimal("5"), "weight_unit_id": "kg"})
    with pytest.raises(InventoryInvalidReference, match="so se aplica"):
        service._validate_item_refs({"unit_id": "kg", "weight_quantity": Decimal("5"), "weight_unit_id": "kg"})
    package.has_weight = True
    with pytest.raises(InventoryInvalidReference, match="exige o peso total"):
        service._validate_item_refs({"unit_id": "bucket", "weight_quantity": None, "weight_unit_id": None})
