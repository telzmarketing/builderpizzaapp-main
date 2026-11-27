from decimal import Decimal

import pytest
from pydantic import ValidationError

import backend.main  # noqa: F401 - load the complete SQLAlchemy registry
from backend.core.exceptions import DomainError
from backend.models.strategic_campaign import StrategicOffer
from backend.schemas.order import CheckoutIn, DeliveryAddressIn, StrategicOfferGroupIn
from backend.schemas.strategic_campaign import StrategicOfferCreate
from backend.services.strategic_campaign_service import StrategicCampaignService
from backend.services.strategic_offer_composition_service import StrategicOfferCompositionService


def _offer_payload(**overrides):
    payload = {
        "code": "BLACK-3",
        "title": "Duas tradicionais e uma especial",
        "reference_type": "mixed_subcategories",
        "components": [
            {"subcategory_id": "traditional", "quantity": 2},
            {"subcategory_id": "special", "quantity": 1},
        ],
        "pricing_strategy": "fixed_price",
        "fixed_promotional_price": Decimal("99.90"),
        "price_original": Decimal("150.00"),
        "price_promotional": Decimal("99.90"),
    }
    payload.update(overrides)
    return payload


def _cart_item(product_id="pizza-1"):
    return {
        "product_id": product_id,
        "quantity": 1,
        "selected_size": "Grande",
        "selected_size_id": "size-g",
        "flavor_division": 1,
        "flavors": [],
        "final_price": 50,
        "add_ons": [],
    }


def test_legacy_product_reference_is_inferred():
    offer = StrategicOfferCreate(
        code="PRODUCT",
        title="Produto",
        product_id="product-1",
        price_original=Decimal("50.00"),
        price_promotional=Decimal("50.00"),
    )
    assert offer.reference_type == "product"


def test_single_subcategory_requires_exactly_one_component():
    payload = _offer_payload(reference_type="subcategory", components=[])
    with pytest.raises(ValidationError):
        StrategicOfferCreate(**payload)


def test_mixed_subcategories_accepts_ordered_variable_quantities():
    offer = StrategicOfferCreate(**_offer_payload())
    assert [(row.subcategory_id, row.quantity) for row in offer.components] == [
        ("traditional", 2),
        ("special", 1),
    ]


def test_mixed_subcategories_rejects_duplicate_subcategory():
    payload = _offer_payload(components=[
        {"subcategory_id": "traditional", "quantity": 2},
        {"subcategory_id": "traditional", "quantity": 1},
    ])
    with pytest.raises(ValidationError):
        StrategicOfferCreate(**payload)


def test_percentage_requires_its_percentage_value():
    payload = _offer_payload(
        pricing_strategy="percentage",
        fixed_promotional_price=None,
        discount_percent=None,
    )
    with pytest.raises(ValidationError):
        StrategicOfferCreate(**payload)


def test_pricing_strategy_rejects_values_from_another_strategy():
    payload = _offer_payload(discount_amount=Decimal("10.00"))
    with pytest.raises(ValidationError):
        StrategicOfferCreate(**payload)


@pytest.mark.parametrize(
    ("strategy", "field", "value", "expected"),
    [
        ("catalog", None, None, Decimal("100.00")),
        ("percentage", "discount_percent", Decimal("15"), Decimal("85.00")),
        ("fixed_discount", "discount_amount", Decimal("12.50"), Decimal("87.50")),
        ("fixed_price", "fixed_promotional_price", Decimal("79.90"), Decimal("79.90")),
    ],
)
def test_server_pricing_strategies(strategy, field, value, expected):
    offer = StrategicOffer(pricing_strategy=strategy)
    if field:
        setattr(offer, field, value)
    assert StrategicOfferCompositionService.promotional_total(offer, Decimal("100.00")) == expected


def test_fixed_discount_never_produces_negative_total():
    offer = StrategicOffer(pricing_strategy="fixed_discount", discount_amount=Decimal("120.00"))
    assert StrategicOfferCompositionService.promotional_total(offer, Decimal("100.00")) == Decimal("0.00")


def test_checkout_group_keeps_step_configuration_nested():
    group = StrategicOfferGroupIn(
        offer_id="offer-1",
        campaign_version=3,
        composition_revision=2,
        quantity=1,
        selections=[{"step_key": "component-0:1", "item": _cart_item()}],
    )
    assert group.selections[0].item.product_id == "pizza-1"
    assert group.selections[0].step_key == "component-0:1"


def test_checkout_separates_entry_channel_from_marketing_attribution():
    payload = CheckoutIn(
        items=[],
        strategic_offer_groups=[{
            "offer_id": "offer-1",
            "campaign_version": 1,
            "composition_revision": 1,
            "quantity": 1,
            "selections": [{"step_key": "component-0:1", "item": _cart_item()}],
        }],
        delivery=DeliveryAddressIn(name="Cliente", phone="5511999999999", street="Rua 1", city="SP"),
        entry_channel="pdv",
        utm_campaign="paid-black-friday",
    )
    assert payload.entry_channel == "pdv"
    assert payload.utm_campaign == "paid-black-friday"


def test_invalid_entry_channel_fails_closed():
    with pytest.raises(DomainError) as error:
        StrategicOfferCompositionService._assert_channel("marketplace")
    assert error.value.code == "InvalidStrategicEntryChannel"


def test_partial_update_cannot_leave_pricing_strategy_without_its_value():
    with pytest.raises(DomainError) as error:
        StrategicCampaignService._assert_pricing_strategy("percentage", None, None, None)
    assert error.value.code == "InvalidStrategicOfferPricingStrategy"


def test_partial_update_cannot_keep_value_from_another_pricing_strategy():
    with pytest.raises(DomainError) as error:
        StrategicCampaignService._assert_pricing_strategy(
            "fixed_price",
            Decimal("10"),
            None,
            Decimal("79.90"),
        )
    assert error.value.code == "InvalidStrategicOfferPricingStrategy"
