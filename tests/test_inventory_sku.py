from types import SimpleNamespace

from backend.schemas.inventory import InventoryItemIn
from backend.services.inventory_service import InventoryService


class _Query:
    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return None


class _Db:
    def query(self, _model):
        return _Query()

    def commit(self):
        return None

    def refresh(self, _row):
        return None


def test_create_item_generates_sku_when_omitted(monkeypatch):
    service = InventoryService(_Db(), "tenant-a")
    captured = {}
    row = SimpleNamespace()

    def create(_model, data, _prefix, *, commit=False):
        captured.update(data)
        return row

    monkeypatch.setattr(service, "_create", create)
    monkeypatch.setattr(service, "_validate_item_refs", lambda _data: None)
    monkeypatch.setattr(service, "_serialize_item", lambda _row: {"sku": captured["sku"]})

    result = service.create_item(InventoryItemIn(name="Mussarela"))

    assert result["sku"].startswith("INS-")
    assert len(result["sku"]) == 14


def test_create_item_preserves_explicit_sku_for_compatibility(monkeypatch):
    service = InventoryService(_Db(), "tenant-a")
    captured = {}
    row = SimpleNamespace()

    monkeypatch.setattr(service, "_create", lambda _model, data, _prefix, *, commit=False: (captured.update(data) or row))
    monkeypatch.setattr(service, "_validate_item_refs", lambda _data: None)
    monkeypatch.setattr(service, "_serialize_item", lambda _row: captured)

    service.create_item(InventoryItemIn(name="Mussarela", sku="FORN-001"))

    assert captured["sku"] == "FORN-001"


def test_create_non_ingredient_does_not_receive_ingredient_sku(monkeypatch):
    service = InventoryService(_Db(), "tenant-a")
    captured = {}
    row = SimpleNamespace()

    monkeypatch.setattr(service, "_create", lambda _model, data, _prefix, *, commit=False: (captured.update(data) or row))
    monkeypatch.setattr(service, "_validate_item_refs", lambda _data: None)
    monkeypatch.setattr(service, "_serialize_item", lambda _row: captured)

    service.create_item(InventoryItemIn(name="Caixa", item_type="packaging"))

    assert captured["sku"] is None
