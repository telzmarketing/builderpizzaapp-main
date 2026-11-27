from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from copy import deepcopy

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main  # noqa: F401 - load the complete SQLAlchemy registry
from backend.core.exceptions import DomainError
from backend.database import Base
from backend.models.product import Product, ProductCategory, ProductCrustType, ProductDrinkVariant, ProductOption, ProductOptionGroup, ProductSize
from backend.models.gestao import GestaoModuleSettings
from backend.models.strategic_campaign import (
    StrategicCampaign,
    StrategicCampaignStatus,
    StrategicCampaignVersion,
    StrategicOffer,
    StrategicOfferComponent,
)
from backend.schemas.order import StrategicOfferGroupIn
from backend.services.strategic_offer_composition_service import StrategicOfferCompositionService


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            ProductCategory.__table__,
            Product.__table__,
            ProductSize.__table__,
            ProductCrustType.__table__,
            ProductDrinkVariant.__table__,
            ProductOptionGroup.__table__,
            ProductOption.__table__,
            GestaoModuleSettings.__table__,
            StrategicCampaign.__table__,
            StrategicOffer.__table__,
            StrategicOfferComponent.__table__,
            StrategicCampaignVersion.__table__,
        ],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def _cart_item(product_id="product-1", **overrides):
    payload = {
        "product_id": product_id,
        "quantity": 1,
        "selected_size": "Grande",
        "selected_size_id": "size-g",
        "selected_crust_type_id": "crust-thin",
        "selected_border_id": "border-cheese",
        "flavor_division": 2,
        "flavors": [],
        "final_price": 50,
        "add_ons": [],
        "option_selections": [{"group_id": "extras", "option_id": "option-bacon"}],
    }
    payload.update(overrides)
    return payload


def _group(offer_id="offer-1", *, quantity=1, selections=None, revision=1):
    if selections is None:
        selections = [{"step_key": "product:1", "item": _cart_item()}]
    return StrategicOfferGroupIn(
        offer_id=offer_id,
        campaign_version=1,
        composition_revision=revision,
        quantity=quantity,
        selections=selections,
    )


def _seed(
    db,
    *,
    reference_type="product",
    product_id="product-1",
    components=None,
    starts_at=None,
    ends_at=None,
    pricing_strategy="fixed_price",
    discount_amount=None,
    fixed_price="39.90",
    quantity_limit=10,
    config=None,
):
    parent = ProductCategory(id="category", tenant_id="tenant-1", name="Pizzas", active=True)
    child = ProductCategory(id="subcategory", tenant_id="tenant-1", parent_id="category", name="Tradicionais", active=True)
    products = [
        Product(id="product-1", tenant_id="tenant-1", name="Calabresa", description="Pizza", price=50, subcategory_id="subcategory", active=True),
        Product(id="product-2", tenant_id="tenant-1", name="Mussarela", description="Pizza", price=45, subcategory_id="subcategory", active=True),
    ]
    campaign = StrategicCampaign(
        id="campaign-1",
        tenant_id="tenant-1",
        name="Campanha viva editavel",
        commercial_name="Campanha viva editavel",
        slug="campanha-viva",
        status=StrategicCampaignStatus.active,
        starts_at=None,
        ends_at=None,
        visual_config={},
        commercial_config={},
        marketing_config={},
        published_version=1,
    )
    live_offer = StrategicOffer(
        id="offer-1",
        tenant_id="tenant-1",
        campaign_id=campaign.id,
        code="LIVE",
        title="Oferta viva editavel",
        product_id=product_id if reference_type == "product" else None,
        reference_type=reference_type,
        pricing_strategy=pricing_strategy,
        discount_amount=Decimal(discount_amount) if discount_amount is not None else None,
        fixed_promotional_price=Decimal(fixed_price) if fixed_price is not None else None,
        composition_revision=1,
        price_original=Decimal("50.00"),
        price_promotional=Decimal(fixed_price or "40.00"),
        active=True,
        display_order=0,
        quantity_limit=quantity_limit,
        config=config or {},
    )
    snapshot_components = components or []
    snapshot = {
        "schema_version": 1,
        "campaign": {
            "id": campaign.id,
            "name": "Campanha publicada",
            "commercial_name": "Campanha publicada",
            "slug": "campanha-publicada",
            "status": "active",
            "starts_at": starts_at.isoformat() if starts_at else None,
            "ends_at": ends_at.isoformat() if ends_at else None,
            "visual_config": {},
            "commercial_config": {},
            "marketing_config": {},
            "published_version": 1,
        },
        "offers": [{
            "id": live_offer.id,
            "campaign_id": campaign.id,
            "code": "PUBLISHED",
            "title": "Oferta publicada",
            "product_id": product_id if reference_type == "product" else None,
            "kit_id": "kit-1" if reference_type == "kit" else None,
            "reference_type": reference_type,
            "components": snapshot_components,
            "pricing_strategy": pricing_strategy,
            "discount_amount": discount_amount,
            "fixed_promotional_price": fixed_price,
            "composition_revision": 1,
            "price_original": "50.00",
            "price_promotional": fixed_price or "40.00",
            "active": True,
            "display_order": 0,
            "quantity_limit": quantity_limit,
            "max_per_customer": None,
            "show_when_sold_out": True,
            "config": config or {},
        }],
    }
    version = StrategicCampaignVersion(
        id="version-1",
        tenant_id="tenant-1",
        campaign_id=campaign.id,
        version=1,
        snapshot=snapshot,
    )
    db.add_all([parent, child, *products, campaign, live_offer, version])
    db.commit()
    return campaign, live_offer


def test_mixed_selection_groups_generate_independent_steps_and_validate_membership(db):
    _seed(
        db,
        reference_type="mixed_subcategories",
        product_id=None,
        components=[
            {"subcategory_id": "subcategory", "quantity": 1, "allow_repeated_products": False},
            {"subcategory_id": "drinks", "quantity": 1, "allow_repeated_products": True},
        ],
        config={
            "selection_groups": [
                {"subcategory_ids": ["subcategory"], "quantity": 2, "title": "Pizzas"},
                {"subcategory_ids": ["drinks"], "quantity": 1, "title": "Bebidas"},
            ],
        },
    )
    db.add(ProductCategory(id="drinks-parent", tenant_id="tenant-1", name="Bebidas Gerais", active=True))
    db.add(ProductCategory(id="drinks", tenant_id="tenant-1", parent_id="drinks-parent", name="Refrigerantes", active=True))
    db.add(Product(id="drink-1", tenant_id="tenant-1", name="Refrigerante", description="Bebida", price=8, subcategory_id="drinks", active=True))
    db.commit()

    service = StrategicOfferCompositionService(db, "tenant-1")
    configuration = service.configuration("offer-1", 1)
    assert [step["step_key"] for step in configuration["steps"]] == [
        "selection-group-1:1",
        "selection-group-1:2",
        "selection-group-2:1",
    ]
    assert [step["title"] for step in configuration["steps"]] == ["Pizzas", "Pizzas", "Bebidas"]
    assert configuration["selection_groups"][0]["quantity"] == 2

    selections = [
        {"step_key": "selection-group-1:1", "item": _cart_item("product-1")},
        {"step_key": "selection-group-1:2", "item": _cart_item("product-2")},
        {"step_key": "selection-group-2:1", "item": _cart_item("drink-1")},
    ]
    items, resolved = service.expand_groups([_group(selections=selections)])
    assert [item.product_id for item in items] == ["product-1", "product-2", "drink-1"]
    assert resolved[0].item_count == 3

    invalid = [
        {"step_key": "selection-group-1:1", "item": _cart_item("product-1")},
        {"step_key": "selection-group-1:2", "item": _cart_item("product-2")},
        {"step_key": "selection-group-2:1", "item": _cart_item("product-1")},
    ]
    with pytest.raises(DomainError) as error:
        service.expand_groups([_group(selections=invalid)])
    assert error.value.code == "StrategicOfferProductInvalid"


def test_mixed_selection_groups_keep_repetition_rule_scoped_to_each_group(db):
    _seed(
        db,
        reference_type="mixed_subcategories",
        product_id=None,
        components=[
            {"subcategory_id": "subcategory", "quantity": 1, "allow_repeated_products": False},
            {"subcategory_id": "drinks", "quantity": 1, "allow_repeated_products": True},
        ],
        config={
            "selection_groups": [
                {"subcategory_ids": ["subcategory"], "quantity": 2},
                {"subcategory_ids": ["drinks"], "quantity": 1},
            ],
        },
    )
    db.add(ProductCategory(id="drinks-parent", tenant_id="tenant-1", name="Bebidas Gerais", active=True))
    db.add(ProductCategory(id="drinks", tenant_id="tenant-1", parent_id="drinks-parent", name="Refrigerantes", active=True))
    db.add(Product(id="drink-1", tenant_id="tenant-1", name="Refrigerante", description="Bebida", price=8, subcategory_id="drinks", active=True))
    db.commit()

    selections = [
        {"step_key": "selection-group-1:1", "item": _cart_item("product-1")},
        {"step_key": "selection-group-1:2", "item": _cart_item("product-1")},
        {"step_key": "selection-group-2:1", "item": _cart_item("drink-1")},
    ]
    with pytest.raises(DomainError) as error:
        StrategicOfferCompositionService(db, "tenant-1").expand_groups([_group(selections=selections)])
    assert error.value.code == "StrategicOfferRepeatedProduct"


def test_published_snapshot_is_authority_for_configuration_and_checkout(db):
    _, live_offer = _seed(db)
    live_offer.product_id = "product-2"
    live_offer.title = "Edicao ainda nao publicada"
    live_offer.fixed_promotional_price = Decimal("1.00")
    live_offer.composition_revision = 99
    db.commit()

    service = StrategicOfferCompositionService(db, "tenant-1")
    config = service.configuration("offer-1", 1)
    items, resolved = service.expand_groups([_group()])

    assert config["composition_revision"] == 1
    assert config["price_range"]["minimum"] == Decimal("39.90")
    assert config["steps"][0]["eligible_products"][0]["id"] == "product-1"
    assert items[0].product_id == "product-1"
    assert resolved[0].offer.title == "Oferta publicada"


def test_pre_c11_kit_snapshot_infers_reference_type(db):
    _seed(db, reference_type="kit", product_id=None)
    version = db.query(StrategicCampaignVersion).filter_by(id="version-1").one()
    snapshot = deepcopy(version.snapshot)
    snapshot["offers"][0].pop("reference_type", None)
    version.snapshot = snapshot
    db.commit()

    configuration = StrategicOfferCompositionService(db, "tenant-1").configuration("offer-1", 1)

    assert configuration["reference_type"] == "kit"
    assert configuration["steps"][0]["kit_id"] == "kit-1"


@pytest.mark.parametrize(
    ("starts_at", "ends_at"),
    [
        (datetime.now(timezone.utc) + timedelta(hours=1), None),
        (None, datetime.now(timezone.utc) - timedelta(seconds=1)),
    ],
)
def test_campaign_window_guards_listing_configuration_and_checkout(db, starts_at, ends_at):
    _seed(db, starts_at=starts_at, ends_at=ends_at)
    service = StrategicOfferCompositionService(db, "tenant-1")

    assert service.available_campaigns("pdv") == []
    with pytest.raises(DomainError) as list_error:
        service.available_offers("campaign-1", "pdv")
    with pytest.raises(DomainError) as config_error:
        service.configuration("offer-1", 1)
    with pytest.raises(DomainError) as checkout_error:
        service.expand_groups([_group()])

    assert {list_error.value.code, config_error.value.code, checkout_error.value.code} == {"StrategicCampaignUnavailable"}


def test_limits_are_checked_once_with_aggregated_quantity_for_duplicate_offer_groups(db, monkeypatch):
    _seed(db, quantity_limit=1)
    service = StrategicOfferCompositionService(db, "tenant-1")
    checked = []
    monkeypatch.setattr(service, "_assert_purchase_limits", lambda offer, quantity, customer_id, **_: checked.append((offer.id, quantity, customer_id)))

    service.expand_groups([_group(), _group()], customer_id="customer-1", consume_limits=True)

    assert checked == [("offer-1", 2, "customer-1")]


@pytest.mark.parametrize(
    "item_override",
    [
        {"selected_size_id": "size-small"},
        {"selected_crust_type_id": "crust-pan"},
        {"selected_border_id": "border-none"},
        {"option_selections": [{"group_id": "extras", "option_id": "option-onion"}]},
        {"flavor_division": 1},
    ],
)
def test_component_restrictions_are_enforced_on_cart_item(db, item_override):
    restrictions = {
        "size_ids": ["size-g"],
        "crust_ids": ["crust-thin"],
        "border_ids": ["border-cheese"],
        "option_ids": ["option-bacon"],
        "flavor_count": 2,
    }
    _seed(
        db,
        reference_type="subcategory",
        product_id=None,
        components=[{
            "subcategory_id": "subcategory",
            "quantity": 1,
            "allow_repeated_products": True,
            "restrictions": restrictions,
        }],
        pricing_strategy="catalog",
        fixed_price=None,
    )
    selection = {"step_key": "component-0:1", "item": _cart_item(**item_override)}

    with pytest.raises(DomainError) as error:
        StrategicOfferCompositionService(db, "tenant-1").expand_groups([_group(selections=[selection])])

    assert error.value.code == "StrategicOfferRestrictionInvalid"


@pytest.mark.parametrize(
    ("strategy", "discount_amount", "fixed_price", "expected"),
    [
        ("fixed_price", None, "39.90", Decimal("79.80")),
        ("fixed_discount", "10.00", None, Decimal("80.00")),
    ],
)
def test_fixed_pricing_is_applied_per_commercial_quantity(db, strategy, discount_amount, fixed_price, expected):
    _seed(db, pricing_strategy=strategy, discount_amount=discount_amount, fixed_price=fixed_price)
    selections = [
        {"step_key": "group-1:product:1", "item": _cart_item()},
        {"step_key": "group-2:product:1", "item": _cart_item()},
    ]
    _, resolved = StrategicOfferCompositionService(db, "tenant-1").expand_groups([
        _group(quantity=2, selections=selections),
    ])

    assert StrategicOfferCompositionService.promotional_total(resolved[0].offer, Decimal("100.00")) == expected


def test_product_group_requires_one_matching_selection_per_unit(db):
    _seed(db)
    service = StrategicOfferCompositionService(db, "tenant-1")
    wrong_product = [{"step_key": "product:1", "item": _cart_item(product_id="product-2")}]

    with pytest.raises(DomainError) as missing_error:
        service.expand_groups([_group(quantity=2)])
    with pytest.raises(DomainError) as product_error:
        service.expand_groups([_group(selections=wrong_product)])

    assert missing_error.value.code == "StrategicOfferCompositionInvalid"
    assert product_error.value.code == "StrategicOfferProductInvalid"


def test_kit_group_uses_one_matching_selection_per_unit(db):
    _seed(db, reference_type="kit", product_id=None)
    kit_selection = [{"step_key": "kit:1", "item": {"kit_id": "kit-1", "quantity": 1}}]

    service = StrategicOfferCompositionService(db, "tenant-1")
    config = service.configuration("offer-1", 1)
    items, resolved = service.expand_groups([_group(selections=kit_selection)])

    assert config["steps"] == [{
        "key": "kit:1",
        "step_key": "kit:1",
        "position": 0,
        "subcategory_id": None,
        "eligible_products": [],
        "kit_id": "kit-1",
        "restrictions": {},
    }]
    assert items[0].kit_id == "kit-1"
    assert resolved[0].offer.kit_id == "kit-1"
