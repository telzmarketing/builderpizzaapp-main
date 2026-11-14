from types import SimpleNamespace
from datetime import datetime, timezone

from backend.schemas.upsell import UpsellCartItemIn
from backend.services.upsell_engine import UpsellEngine


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return self.rows


class _Db:
    def __init__(self, rows):
        self.rows = rows

    def query(self, _model):
        return _Query(self.rows)


def _upsell(**overrides):
    values = {
        "id": "upsell-1",
        "internal_name": "Oferta",
        "product_id": "offer-product",
        "image_url": None,
        "main_text": "Adicione uma bebida",
        "secondary_text": None,
        "promotional_price": None,
        "trigger_type": "subcategory",
        "trigger_product_id": None,
        "trigger_category": None,
        "trigger_category_id": None,
        "trigger_subcategory": "Bebidas Zero",
        "trigger_subcategory_id": "subcategory-id",
        "trigger_min_value": 0,
        "trigger_min_quantity": 1,
        "allowed_weekdays": "0123456",
        "start_time": None,
        "end_time": None,
        "priority": 0,
        "display_limit": 1,
        "active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "metrics": None,
        "trigger_product": None,
        "product": SimpleNamespace(
            id="offer-product",
            name="Bebida",
            description="",
            price=7.0,
            icon="",
            category="Bebidas",
            subcategory="Bebidas Zero",
            category_id="category-id",
            subcategory_id="subcategory-id",
            product_type="drink",
            active=True,
            sizes=[],
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_engine_matches_subcategory_by_canonical_id():
    result = UpsellEngine(_Db([_upsell()])).get_eligible(
        [UpsellCartItemIn(product_id="pizza", category_id="pizza-category", subcategory_id="subcategory-id")],
        30,
    )

    assert [item.id for item in result] == ["upsell-1"]


def test_engine_keeps_legacy_category_name_trigger_compatible():
    row = _upsell(
        trigger_type="category",
        trigger_category="Pizzas",
        trigger_category_id=None,
        trigger_subcategory=None,
        trigger_subcategory_id=None,
    )
    result = UpsellEngine(_Db([row])).get_eligible(
        [UpsellCartItemIn(product_id="pizza", category="Pizzas")],
        30,
    )

    assert [item.id for item in result] == ["upsell-1"]
