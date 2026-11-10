from decimal import Decimal
from types import SimpleNamespace

from backend.schemas.inventory import InventoryUnitIn
from backend.services.inventory_service import InventoryService


class _Db:
    def commit(self):
        return None

    def refresh(self, _row):
        return None


def _service(monkeypatch, row=None):
    service = InventoryService(_Db(), "tenant-a")
    captured = {}
    monkeypatch.setattr(
        service,
        "_create",
        lambda _model, data, _prefix: (captured.update(data) or SimpleNamespace(**data)),
    )
    monkeypatch.setattr(
        service,
        "_update",
        lambda current, data: (captured.update(data) or current),
    )
    if row is not None:
        monkeypatch.setattr(service, "_get", lambda *_args: row)
    return service, captured


def test_legacy_create_derives_common_mass_and_volume_units(monkeypatch):
    service, captured = _service(monkeypatch)

    service.create_unit(InventoryUnitIn(name="Grama", symbol="gr", unit_type="mass"))
    assert captured["dimension"] == "mass"
    assert captured["conversion_factor"] == Decimal("0.001")

    service.create_unit(InventoryUnitIn(name="Mililitro", symbol="ML", unit_type="volume"))
    assert captured["dimension"] == "volume"
    assert captured["conversion_factor"] == Decimal("0.001")


def test_legacy_create_classifies_unit_and_package_as_count(monkeypatch):
    service, captured = _service(monkeypatch)

    service.create_unit(InventoryUnitIn(name="Cabeça", symbol="CBÇ", unit_type="unit"))
    assert captured["dimension"] == "count"
    assert captured["conversion_factor"] == Decimal("1")

    service.create_unit(InventoryUnitIn(name="Balde", symbol="BLD", unit_type="package"))
    assert captured["dimension"] == "count"
    assert captured["conversion_factor"] == Decimal("1")


def test_legacy_mass_custom_unit_remains_pending(monkeypatch):
    service, captured = _service(monkeypatch)

    service.create_unit(InventoryUnitIn(name="Saco especial", symbol="SACO", unit_type="mass"))

    assert "dimension" not in captured
    assert "conversion_factor" not in captured


def test_legacy_update_fills_only_unclassified_unit(monkeypatch):
    pending = SimpleNamespace(dimension=None, conversion_factor=None, symbol="KG", unit_type="mass")
    service, captured = _service(monkeypatch, pending)

    service.update_unit("kg", InventoryUnitIn(name="Quilo", symbol="KG", unit_type="mass"))

    assert captured["dimension"] == "mass"
    assert captured["conversion_factor"] == Decimal("1")


def test_legacy_update_preserves_existing_technical_classification(monkeypatch):
    classified = SimpleNamespace(dimension="mass", conversion_factor=Decimal("0.001"), symbol="GR", unit_type="mass")
    service, captured = _service(monkeypatch, classified)

    service.update_unit("gr", InventoryUnitIn(name="Grama", symbol="GR", unit_type="mass"))

    assert "dimension" not in captured
    assert "conversion_factor" not in captured
