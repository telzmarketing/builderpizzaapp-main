from types import SimpleNamespace as S

import pytest

from backend.core.exceptions import DomainError
from backend.models.product import Product, ProductCrustType, ProductDrinkVariant, ProductSize
from backend.schemas.order import CartItemIn
from backend.services.order_service import OrderService


class Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *expressions):
        rows = self.rows
        for expression in expressions:
            key = expression.left.key
            value = True if str(expression.right) == "true" else expression.right.value
            rows = [row for row in rows if getattr(row, key, None) == value]
        return Query(rows)

    def first(self):
        return next(iter(self.rows), None)


def make_service():
    option = S(id="meat", name="Carne", active=True, price_addition=4)
    group = S(id="filling", name="Recheio", active=True, selection_type="single", required=True,
              min_selections=1, max_selections=1, options=[option])
    product = S(id="esfiha", tenant_id="tenant-legacy-default", name="Esfirra", price=10,
                delivery_price=10, dine_in_price=10, active=True, product_type="other",
                visible_delivery=True, visible_dine_in=True, category="Esfirras", subcategory=None,
                sizes=[], promotions=[],
                icon="", option_groups=[group])
    rows = {Product: [product], ProductSize: [], ProductCrustType: [], ProductDrinkVariant: []}
    db = S(query=lambda model: Query(rows.get(model, [])))
    return product, group, OrderService(db)


def make_cart(**values):
    return CartItemIn(**({
        "product_id": "esfiha",
        "quantity": 1,
        "selected_size": "Unico",
        "flavors": [{"product_id": "esfiha", "name": "Esfirra", "price": 10, "icon": ""}],
        "final_price": 0,
    } | values))


def config():
    return S(max_flavors=3, flavor_category_filters=[], pricing_rule="average")


def test_configurable_options_are_validated_and_server_priced():
    _, _, service = make_service()
    item = make_cart(option_selections=[{
        "group_id": "filling", "group_name": "Falsificado", "option_id": "meat",
        "label": "Falsificado", "price_addition": 0,
    }])

    price, *_ = service._validate_item(item, config())

    assert price == 14
    assert item.option_selections[0]["group_name"] == "Recheio"
    assert item.option_selections[0]["label"] == "Carne"
    assert item.option_selections[0]["price_addition"] == 4


def test_required_configurable_option_cannot_be_omitted():
    _, _, service = make_service()

    with pytest.raises(DomainError) as error:
        service._validate_item(make_cart(), config())

    assert error.value.code == "InvalidProductOptionSelection"


def test_unknown_configurable_option_is_rejected():
    _, _, service = make_service()
    item = make_cart(option_selections=[{"group_id": "filling", "option_id": "foreign"}])

    with pytest.raises(DomainError) as error:
        service._validate_item(item, config())

    assert error.value.code == "InvalidProductOptionSelection"
