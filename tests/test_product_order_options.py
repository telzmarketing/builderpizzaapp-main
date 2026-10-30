from types import SimpleNamespace as S

import pytest

from backend.core.exceptions import DomainError, InvalidStatusTransition
from backend.core.state_machine import order_sm
from backend.models.product import Product, ProductCrustType, ProductDrinkVariant, ProductSize, PricingRule
from backend.schemas.order import CartItemIn
from backend.services.order_service import OrderService
from backend.services.product_pricing_service import ProductPricingService


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


@pytest.fixture
def catalog():
    product = S(id="pizza", tenant_id="tenant-legacy-default", name="Pizza", price=30,
                delivery_price=35, dine_in_price=32, active=True, product_type="pizza",
                visible_delivery=True, visible_dine_in=True, category="Pizzas", subcategory=None,
                sizes=[], promotions=[], icon="")
    rows = {Product: [product], ProductSize: [], ProductCrustType: [], ProductDrinkVariant: []}
    db = S(query=lambda model: Query(rows.get(model, [])))
    return product, rows, OrderService(db)


def cart(**values):
    return CartItemIn(**({"product_id": "pizza", "quantity": 1, "selected_size": "Forged label",
                         "flavors": [{"product_id": "pizza", "name": "Forged name", "price": .01, "icon": ""}],
                         "final_price": .01} | values))


def config(rule=PricingRule.average):
    return S(max_flavors=3, flavor_category_filters=[], pricing_rule=rule)


@pytest.mark.parametrize("field", ["selected_size_id", "selected_crust_type_id", "selected_border_id", "selected_drink_variant_id"])
def test_unknown_options_are_rejected(catalog, field):
    _, _, service = catalog
    with pytest.raises(DomainError, match="inexistente"):
        service._validate_item(cart(**{field: "unknown"}), config())


def test_missing_required_size_cannot_buy_large_at_base_price(catalog):
    product, _, service = catalog
    product.sizes = [S(active=True)]
    with pytest.raises(DomainError) as error:
        service._validate_item(cart(), config())
    assert error.value.code == "ProductSizeRequired"


def test_options_use_database_names_and_channel_price(catalog):
    _, rows, service = catalog
    rows[ProductCrustType] = [S(id="border", product_id="pizza", tenant_id="tenant-legacy-default", active=True, name="Catupiry", price_addition=8, option_kind="border")]
    item = cart(selected_border_id="border", selected_border_name="FREE")
    price, *_ = service._validate_item(item, config())
    assert price == 43
    assert item.selected_border_name == "Catupiry"
    assert item.selected_size == "Unico"
    assert service._validate_item(cart(), config(), channel="dine_in")[0] == 32


def test_product_can_disable_crust_and_border_options(catalog):
    product, rows, service = catalog
    product.show_crust_options = False
    rows[ProductCrustType] = [S(
        id="crust", product_id="pizza", tenant_id="tenant-legacy-default",
        active=True, name="Massa Tradicional", price_addition=0,
    )]
    with pytest.raises(DomainError, match="nao permite selecionar"):
        service._validate_item(cart(selected_crust_type_id="crust"), config())


@pytest.mark.parametrize("field,kind", [("selected_crust_type_id", "border"), ("selected_border_id", "dough")])
def test_order_rejects_option_of_wrong_kind(catalog, field, kind):
    _, rows, service = catalog
    rows[ProductCrustType] = [S(id="option", product_id="pizza", tenant_id="tenant-legacy-default",
                              active=True, name="Arbitrary", price_addition=8, option_kind=kind)]
    with pytest.raises(DomainError) as error:
        service._validate_item(cart(**{field: "option"}), config())
    assert error.value.code == "InvalidProductOptionKind"


@pytest.mark.parametrize("field,disabled", [("selected_crust_type_id", "enable_dough"), ("selected_border_id", "enable_border")])
def test_order_respects_independent_category_capabilities(catalog, monkeypatch, field, disabled):
    _, _, service = catalog
    monkeypatch.setattr("backend.services.order_service.effective_capabilities", lambda *_: {
        "enable_sizes": False, "enable_dough": disabled != "enable_dough",
        "enable_border": disabled != "enable_border", "enable_product_options": False,
        "enable_promotions": False,
    })
    with pytest.raises(DomainError, match="nao permite selecionar"):
        service._validate_item(cart(**{field: "option"}), config())


def test_valid_size_takes_precedence_over_channel_price(catalog):
    product, rows, service = catalog
    size = S(id="large", product_id="pizza", tenant_id="tenant-legacy-default", active=True, label="Grande", price=80)
    product.sizes = rows[ProductSize] = [size]
    item = cart(selected_size_id="large")
    assert service._validate_item(item, config())[0] == 80
    assert item.selected_size == "Grande"


def test_inactive_foreign_and_hidden_options_are_rejected(catalog):
    product, rows, service = catalog
    rows[ProductCrustType] = [S(id="foreign", product_id="different", tenant_id="tenant-legacy-default", active=True)]
    with pytest.raises(DomainError):
        service._validate_item(cart(selected_border_id="foreign"), config())
    rows[ProductCrustType] = [S(id="foreign", product_id="pizza", tenant_id="another-tenant", active=True)]
    with pytest.raises(DomainError):
        service._validate_item(cart(selected_border_id="foreign"), config())
    product.visible_delivery = False
    with pytest.raises(DomainError) as error:
        service._validate_item(cart(), config())
    assert error.value.code == "ProductChannelUnavailable"


def test_single_flavor_cannot_replace_primary_product(catalog):
    product, rows, service = catalog
    rows[Product].append(S(**(vars(product) | {"id": "cheap", "price": 1, "delivery_price": 1})))
    with pytest.raises(DomainError) as error:
        service._validate_item(cart(flavors=[{"product_id": "cheap", "name": "", "price": 1, "icon": ""}]), config())
    assert error.value.code == "InvalidPrimaryFlavor"


@pytest.mark.parametrize("kind", ["pickup", "dine_in"])
def test_local_completion_uses_context_without_global_shortcut(kind):
    assert not order_sm.can_transition("ready_for_pickup", "delivered")
    result = order_sm.complete_local_fulfillment("order", "ready_for_pickup", fulfillment_type=kind)
    assert result.to_status == "delivered"


@pytest.mark.parametrize("status,kind", [("preparing", "dine_in"), ("ready_for_pickup", "delivery")])
def test_local_completion_rejects_wrong_stage_or_delivery(status, kind):
    with pytest.raises(InvalidStatusTransition):
        order_sm.complete_local_fulfillment("order", status, fulfillment_type=kind)


def test_changed_total_requires_explicit_reconfirmation():
    with pytest.raises(DomainError) as error:
        OrderService._validate_expected_total(40, 40.01)
    assert error.value.code == "CheckoutPriceChanged"
    OrderService._validate_expected_total(40, 40)
    OrderService._validate_expected_total(None, 99)
