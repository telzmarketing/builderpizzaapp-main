from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main  # noqa: F401
from backend.core.exceptions import DomainError
from backend.database import Base
from backend.models.product import Product, ProductCategory
from backend.models.strategic_campaign import StrategicCampaign, StrategicOffer, StrategicOfferComponent
from backend.schemas.strategic_campaign import StrategicOfferCreate
from backend.services.strategic_campaign_service import StrategicCampaignService
from backend.services.strategic_offer_composition_service import StrategicOfferCompositionService


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        ProductCategory.__table__, Product.__table__, StrategicCampaign.__table__,
        StrategicOffer.__table__, StrategicOfferComponent.__table__,
    ])
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(
        "backend.services.inventory_service.ProductInventoryAvailabilityService.product_payloads",
        lambda self, product_ids: {product_id: {"inventory_available": True} for product_id in product_ids},
    )
    yield session
    session.close()
    engine.dispose()


def _catalog(db):
    pizzas = ProductCategory(id="cat-pizzas", tenant_id="tenant-1", name="Pizzas", active=True)
    drinks = ProductCategory(id="cat-drinks", tenant_id="tenant-1", name="Bebidas", active=True)
    traditional = ProductCategory(id="sub-traditional", tenant_id="tenant-1", parent_id=pizzas.id, name="Tradicionais", active=True)
    db.add_all([pizzas, drinks, traditional])
    db.add_all([
        Product(id="pizza-1", tenant_id="tenant-1", name="Pizza", description="", price=50, active=True, category_id=pizzas.id, subcategory_id=traditional.id),
        Product(id="drink-1", tenant_id="tenant-1", name="Refrigerante", description="", price=8, active=True, category_id=drinks.id, subcategory_id=None),
        Product(id="drink-other-tenant", tenant_id="tenant-2", name="Outro", description="", price=8, active=True, category_id=drinks.id, subcategory_id=None),
    ])
    campaign = StrategicCampaign(id="campaign-1", tenant_id="tenant-1", name="Campanha", slug="campanha")
    db.add(campaign)
    db.commit()
    return campaign


def _payload():
    return StrategicOfferCreate(
        code="PIZZA-DRINK",
        title="Pizza e bebida",
        reference_type="mixed_subcategories",
        components=[{"subcategory_id": "sub-traditional", "quantity": 1}],
        config={"selection_groups": [
            {"category_id": "cat-pizzas", "subcategory_ids": ["sub-traditional"], "quantity": 1},
            {"category_id": "cat-drinks", "product_ids": ["drink-1"], "quantity": 1},
        ]},
        price_original=Decimal("58.00"),
        price_promotional=Decimal("49.90"),
    )


def test_schema_accepts_independent_direct_category_group():
    offer = _payload()
    groups = offer.config["selection_groups"]
    assert groups[0]["subcategory_ids"] == ["sub-traditional"]
    assert groups[1]["product_ids"] == ["drink-1"]


def test_create_validates_direct_products_against_active_root_category(db):
    campaign = _catalog(db)
    offer = StrategicCampaignService(db, "tenant-1").add_offer(campaign.id, _payload())
    assert offer.config["selection_groups"][1]["product_ids"] == ["drink-1"]


def test_create_rejects_direct_product_from_another_tenant(db):
    campaign = _catalog(db)
    payload = _payload()
    payload.config["selection_groups"][1]["product_ids"] = ["drink-other-tenant"]
    with pytest.raises(DomainError) as error:
        StrategicCampaignService(db, "tenant-1").add_offer(campaign.id, payload)
    assert error.value.code == "StrategicOfferProductNotFound"


def test_direct_category_group_resolves_only_products_without_subcategory(db):
    _catalog(db)
    service = StrategicOfferCompositionService(db, "tenant-1")
    products = service._eligible_products_for_selection_group({
        "category_id": "cat-drinks", "product_ids": ["drink-1"], "subcategory_ids": [],
    })
    assert [product.id for product in products] == ["drink-1"]

