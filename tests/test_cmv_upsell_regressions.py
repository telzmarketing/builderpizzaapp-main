from types import SimpleNamespace

from backend.models.product import Product
from backend.models.upsell import UpsellMetric
from backend.schemas.upsell import UpsellIn
from backend.services.cmv_service import CmvService
from backend.services.upsell_engine import UpsellEngine


class _Query:
    def __init__(self, result):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.result if isinstance(self.result, list) else ([] if self.result is None else [self.result])

    def first(self):
        return self.result


class _CmvDb:
    def __init__(self, product):
        self.product = product

    def query(self, model):
        assert model is Product
        return _Query([self.product])


def test_cmv_lists_active_pizza_without_recipe_as_missing_recipe():
    pizza = SimpleNamespace(
        id="pizza-sem-ficha",
        name="Pizza sem ficha",
        product_type="pizza",
        price=48.0,
        active=True,
    )
    service = CmvService.__new__(CmvService)
    service._db = _CmvDb(pizza)
    service._tenant_id = "tenant-a"
    service._settings = lambda: SimpleNamespace(enabled=True, status="enabled")
    service._recipe_map = lambda product_ids: {}
    service._unit_cost_map = lambda: {}
    service._snapshot_summary = lambda: {
        "count": 0,
        "sale_total": 0.0,
        "cost_total": 0.0,
        "cmv_percent": None,
        "pending_count": 0,
    }

    result = service.overview()

    assert [row["product_name"] for row in result["products"]] == ["Pizza sem ficha"]
    assert result["products_missing_recipe"] == 1
    assert result["products"][0]["status"] == "missing_recipe"
    assert result["products"][0]["has_recipe"] is False


class _UpsellDb:
    def __init__(self, product):
        self.product = product
        self.added = []
        self.committed = False
        self.rolled_back = False

    def query(self, model):
        if model is Product:
            return _Query(self.product)
        if model is UpsellMetric or getattr(model, "__name__", "") == "DummyMetric":
            return _Query(None)
        raise AssertionError(f"consulta inesperada: {model}")

    def add(self, value):
        self.added.append(value)

    def flush(self):
        return None

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, value):
        return None


def test_upsell_creation_sets_tenant_and_creates_metrics(monkeypatch):
    class DummyUpsell:
        def __init__(self, **values):
            self.__dict__.update(values)

    class DummyMetric:
        upsell_id = None

        def __init__(self, **values):
            self.__dict__.update(values)

    product = SimpleNamespace(active=True)
    db = _UpsellDb(product)
    monkeypatch.setattr("backend.services.upsell_engine.Upsell", DummyUpsell)
    monkeypatch.setattr("backend.services.upsell_engine.UpsellMetric", DummyMetric)
    monkeypatch.setattr("backend.services.upsell_engine._serialize_upsell", lambda row: row)
    data = UpsellIn(
        internal_name="Pizza doce",
        product_id="product-1",
        main_text="Leve uma pizza doce",
        trigger_type="min_value",
        trigger_min_value=30,
    )

    created = UpsellEngine(db, "tenant-a").create_upsell(data)

    assert created.tenant_id == "tenant-a"
    metric = next(item for item in db.added if isinstance(item, DummyMetric))
    assert metric.tenant_id == "tenant-a"
    assert db.committed is True
    assert db.rolled_back is False


def test_upsell_creation_rejects_product_from_another_tenant():
    db = _UpsellDb(None)
    data = UpsellIn(
        internal_name="Pizza doce",
        product_id="product-from-other-tenant",
        main_text="Leve uma pizza doce",
    )

    try:
        UpsellEngine(db, "tenant-a").create_upsell(data)
    except UpsellEngine.ValidationError as exc:
        assert "estabelecimento" in str(exc)
    else:
        raise AssertionError("a criação deveria rejeitar produto fora do tenant")
