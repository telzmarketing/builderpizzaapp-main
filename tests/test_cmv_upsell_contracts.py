from types import SimpleNamespace

from backend.models.product import Product
from backend.schemas.upsell import UpsellIn
from backend.services.cmv_service import CmvService
from backend.services import upsell_engine
from backend.services.upsell_engine import UpsellEngine


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows


class _UpsellDb:
    def __init__(self, product, tenant_id="tenant-1"):
        self.product = product
        self.tenant_id = tenant_id
        self.metric = None

    def query(self, model):
        if model.__name__ == "Product":
            return _Query([self.product] if self.product.tenant_id == self.tenant_id else [])
        return _Query([self.metric] if self.metric else [])

    def add(self, value):
        if hasattr(value, "upsell_id"):
            self.metric = value

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, _value):
        return None


class _UpsellRow:
    def __init__(self, **values):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        values.setdefault("created_at", now)
        values.setdefault("updated_at", now)
        self.__dict__.update(values)
        self.product = None
        self.trigger_product = None
        self.metrics = None


class _Metric:
    upsell_id = object()
    tenant_id = object()

    def __init__(self, **values):
        self.__dict__.update(values)


class _CmvDb:
    def __init__(self, products):
        self.products = products

    def query(self, _model):
        return _Query(self.products)


def test_cmv_lists_active_pizza_without_recipe_as_missing_recipe():
    pizza = SimpleNamespace(
        id="pizza-sem-ficha", tenant_id="tenant-1", name="Pizza sem ficha",
        description="", price=42.0, product_type="pizza", active=True,
    )
    service = CmvService(_CmvDb([pizza]), tenant_id="tenant-1")
    service._settings = lambda: None
    service._recipe_map = lambda _ids: {}
    service._unit_cost_map = lambda: {}
    service._snapshot_summary = lambda: {
        "count": 0,
        "sale_total": 0.0,
        "cost_total": 0.0,
        "cmv_percent": None,
        "pending_count": 0,
    }

    result = service.overview()

    assert result["products_total"] == 1
    assert result["products_missing_recipe"] == 1
    assert result["products"][0]["product_name"] == "Pizza sem ficha"
    assert result["products"][0]["has_recipe"] is False
    assert result["products"][0]["status"] == "missing_recipe"


def test_upsell_creation_assigns_tenant_and_creates_metrics(monkeypatch):
    product = SimpleNamespace(
        id="drink-1", tenant_id="tenant-1", name="Refrigerante",
        description="", price=8.0, product_type="drink", active=True,
    )
    product.sizes = []
    db = _UpsellDb(product)
    monkeypatch.setattr(upsell_engine, "Upsell", _UpsellRow)
    monkeypatch.setattr(upsell_engine, "UpsellMetric", _Metric)

    result = UpsellEngine(db, tenant_id="tenant-1").create_upsell(
        UpsellIn(
            internal_name="Oferta bebida",
            product_id="drink-1",
            main_text="Adicione uma bebida",
        )
    )

    assert result.product_id == "drink-1"
    assert db.metric is not None
    assert db.metric.tenant_id == "tenant-1"


def test_upsell_creation_rejects_product_from_another_tenant(monkeypatch):
    product = SimpleNamespace(
        id="drink-1", tenant_id="tenant-2", name="Refrigerante",
        description="", price=8.0, product_type="drink", active=True,
    )
    db = _UpsellDb(product)
    monkeypatch.setattr(upsell_engine, "Upsell", _UpsellRow)
    monkeypatch.setattr(upsell_engine, "UpsellMetric", _Metric)

    try:
        UpsellEngine(db, tenant_id="tenant-1").create_upsell(
            UpsellIn(
                internal_name="Oferta bebida",
                product_id="drink-1",
                main_text="Adicione uma bebida",
            )
        )
    except UpsellEngine.ValidationError as exc:
        assert "nao encontrado" in str(exc)
    else:
        raise AssertionError("deveria rejeitar produto fora do tenant")
