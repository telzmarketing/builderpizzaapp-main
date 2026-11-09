from types import SimpleNamespace
from decimal import Decimal

import pytest

from backend.models.inventory import InventoryItem, InventoryUnit
from backend.models.inventory_portion import InventoryPortionConfig
from backend.models import product as _product_models  # noqa: F401
from backend.models import product_promotion as _product_promotion_models  # noqa: F401
from backend.models import tenant as _tenant_models  # noqa: F401
from backend.models import order as _order_models  # noqa: F401
from backend import main as _all_app_models  # noqa: F401
from backend.schemas.inventory_portion import InventoryPortionConfigIn
from backend.services import inventory_portion_service as portion_module
from backend.services.inventory_portion_service import (
    InventoryPortionConfigService,
    PortionConfigInvalid,
)


class _Query:
    def __init__(self, first_value=None):
        self.first_value = first_value

    def options(self, *_args):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args):
        return self

    def first(self):
        return self.first_value

    def all(self):
        return []


class _Db:
    def __init__(self, source, unit):
        self.source = source
        self.unit = unit
        self.added = []

    def query(self, model):
        if model is InventoryItem:
            return _Query(self.source)
        if model is InventoryUnit:
            return _Query(self.unit)
        if model is InventoryPortionConfig:
            return _Query(None)
        raise AssertionError(model)

    def add_all(self, rows):
        self.added.extend(rows)

    def flush(self):
        return None

    def refresh(self, _row):
        return None


class _Claim:
    def __init__(self):
        self.record = object()
        self.replay_resource_id = None


class _Idempotency:
    def __init__(self, db, tenant_id):
        self.db = db
        self.completed = []

    def claim(self, key, operation, payload):
        assert key
        assert operation == "inventory.portion_config.create"
        return _Claim()

    def complete(self, record, resource_id):
        self.completed.append(resource_id)

    def abandon(self, record):
        return None


class _UpdateIdempotency(_Idempotency):
    def claim(self, key, operation, payload):
        assert operation == "inventory.portion_config.update"
        return _Claim()


def _body(**overrides):
    values = {
        "source_item_id": "raw-1",
        "portion_weight": "150",
        "unit_id": "unit-g",
        "usage": "mandatory",
        "reference_fraction": "0.5",
        "size": "Grande",
        "min_stock": "10",
        "target_stock": "20",
        "shelf_life_days": 3,
        "yield_percent": "95",
        "loss_percent": "5",
    }
    values.update(overrides)
    return InventoryPortionConfigIn(**values)


def test_create_generates_finished_good_without_replacing_source(monkeypatch):
    source = SimpleNamespace(
        id="raw-1", name="Mussarela", item_type="ingredient", active=True,
        category_id="cat-1", default_location_id="loc-1", portionable=True,
        unit_id="unit-g", weight_unit_id=None,
    )
    unit = SimpleNamespace(id="unit-g", name="Gramas", symbol="g", active=True, dimension="mass", conversion_factor=1)
    db = _Db(source, unit)
    monkeypatch.setattr(portion_module, "IdempotencyService", _Idempotency)
    monkeypatch.setattr(InventoryPortionConfigService, "_portion_count_unit", lambda self: SimpleNamespace(id="unit-portion"))

    row = InventoryPortionConfigService(db, "tenant-a", "admin-a").create(_body(), "portion-create-1")

    output = next(item for item in db.added if isinstance(item, InventoryItem))
    assert output.item_type == "finished_good"
    assert output.unit_id == "unit-portion"
    assert output.tenant_id == "tenant-a"
    assert output.id != source.id
    assert output.name.startswith("Mussarela - porcao")
    assert "150.000000" not in output.name
    assert "1.5E+2" not in output.name
    assert output.sku.startswith("POR-")
    assert row.source_item_id == source.id
    assert row.output_item_id == output.id
    assert source.item_type == "ingredient"


def test_selecting_source_in_portioning_enables_portionable_flag(monkeypatch):
    source = SimpleNamespace(
        id="raw-2", name="Tomate", item_type="ingredient", active=True, portionable=False,
        category_id="cat-1", default_location_id="loc-1", unit_id="unit-g", weight_unit_id=None,
    )
    unit = SimpleNamespace(id="unit-g", name="Gramas", symbol="g", active=True, dimension="mass", conversion_factor=1)
    db = _Db(source, unit)
    monkeypatch.setattr(portion_module, "IdempotencyService", _Idempotency)
    monkeypatch.setattr(InventoryPortionConfigService, "_portion_count_unit", lambda self: SimpleNamespace(id="unit-portion"))

    InventoryPortionConfigService(db, "tenant-a", "admin-a").create(_body(source_item_id="raw-2"), "portion-create-no")
    assert source.portionable is True


def test_create_rejects_unclassified_purchase_unit_before_creating_output(monkeypatch):
    source = SimpleNamespace(
        id="raw-1", name="Calabresa", item_type="ingredient", active=True, portionable=False,
        category_id="cat-1", default_location_id="loc-1", unit_id="legacy-kg", weight_unit_id=None,
        weight_quantity=None,
    )
    unit = SimpleNamespace(id="unit-g", name="Gramas", symbol="GR", active=True, dimension="mass", conversion_factor=1)
    db = _Db(source, unit)
    monkeypatch.setattr(portion_module, "IdempotencyService", _Idempotency)
    monkeypatch.setattr(InventoryPortionConfigService, "_find_unit", lambda self, unit_id: SimpleNamespace(
        id="legacy-kg", name="Quilograma legado", active=True, dimension=None, conversion_factor=None,
    ))

    with pytest.raises(PortionConfigInvalid, match="Classifique a unidade de compra"):
        InventoryPortionConfigService(db, "tenant-a", "admin-a").create(_body(), "invalid-unit")
    assert not db.added


def test_schema_rejects_target_below_minimum():
    with pytest.raises(ValueError, match="target_stock"):
        _body(min_stock="21", target_stock="20")


def test_finished_good_cannot_be_used_as_raw_source(monkeypatch):
    source = SimpleNamespace(id="prepared-1", name="Mussarela porcionada", item_type="finished_good", active=True)
    unit = SimpleNamespace(id="unit-g", symbol="g", active=True)
    db = _Db(source, unit)
    monkeypatch.setattr(portion_module, "IdempotencyService", _Idempotency)

    with pytest.raises(PortionConfigInvalid, match="produto porcionado"):
        InventoryPortionConfigService(db, "tenant-a", "admin-a").create(_body(source_item_id="prepared-1"), "portion-create-2")


def test_existing_portion_config_cannot_change_physical_unit(monkeypatch):
    row = SimpleNamespace(id="portion-1", source_item_id="raw-1", unit_id="unit-g", version=1)
    service = InventoryPortionConfigService(object(), "tenant-a", "admin-a")
    monkeypatch.setattr(service, "_get", lambda _config_id: row)
    monkeypatch.setattr(portion_module, "IdempotencyService", _UpdateIdempotency)

    with pytest.raises(PortionConfigInvalid, match="unidade.*nao pode ser trocada"):
        service.update("portion-1", _body(unit_id="unit-kg"), "portion-update-1")

    assert row.unit_id == "unit-g"
    assert row.version == 1


def test_existing_portion_config_cannot_mix_new_weight_with_old_stock(monkeypatch):
    row = SimpleNamespace(
        id="portion-1", source_item_id="raw-1", unit_id="unit-g", version=1,
        portion_weight=Decimal("150"), reference_fraction=Decimal("0.5"), size="Grande",
    )
    service = InventoryPortionConfigService(object(), "tenant-a", "admin-a")
    monkeypatch.setattr(service, "_get", lambda _config_id: row)
    monkeypatch.setattr(portion_module, "IdempotencyService", _UpdateIdempotency)

    with pytest.raises(PortionConfigInvalid, match="identidade da porcao"):
        service.update("portion-1", _body(portion_weight="200"), "portion-update-weight")
    assert row.portion_weight == Decimal("150")
