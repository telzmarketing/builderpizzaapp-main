from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Load the complete registry before SQLAlchemy configures relationships.
import backend.main  # noqa: F401
from backend.core.exceptions import DomainError
from backend.database import Base
from backend.models.product import Product
from backend.models.product_promotion import ProductPromotion
from backend.models.strategic_campaign import StrategicCampaign, StrategicOffer, StrategicOfferComponent
from backend.schemas.strategic_campaign import StrategicOfferCreate, StrategicOfferUpdate
from backend.services.strategic_campaign_service import StrategicCampaignService


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
            Product.__table__,
            ProductPromotion.__table__,
            StrategicCampaign.__table__,
            StrategicOffer.__table__,
            StrategicOfferComponent.__table__,
        ],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def _campaign(db, *, tenant_id="tenant-1"):
    campaign = StrategicCampaign(
        id=f"campaign-{tenant_id}",
        tenant_id=tenant_id,
        name="Black Friday",
        slug=f"black-friday-{tenant_id}",
        visual_config={},
        commercial_config={},
        marketing_config={},
    )
    db.add(campaign)
    db.commit()
    return campaign


def _product(db, product_id, tenant_id):
    product = Product(
        id=product_id,
        tenant_id=tenant_id,
        name=f"Produto {product_id}",
        description="Produto de teste",
        price=50,
        active=True,
    )
    db.add(product)
    db.commit()
    return product


def _promotion(db, promotion_id, product_id, tenant_id):
    promotion = ProductPromotion(
        id=promotion_id,
        tenant_id=tenant_id,
        product_id=product_id,
        name=f"Promoção {promotion_id}",
        active=True,
    )
    db.add(promotion)
    db.commit()
    return promotion


def _payload(product_id, promotion_id):
    return StrategicOfferCreate(
        code="BLACK-001",
        title="Oferta validada",
        product_id=product_id,
        price_original=Decimal("50.00"),
        price_promotional=Decimal("39.90"),
        config={
            "pricing_mode": "product_promotion",
            "product_promotion_id": promotion_id,
            "restrictions": {
                "size_ids": ["size-1"],
                "crust_ids": ["crust-1"],
                "border_ids": ["border-1"],
                "drink_ids": ["drink-1"],
                "option_ids": ["option-1"],
                "flavor_count": 2,
            },
            "legacy_flag": True,
        },
    )


def test_config_validates_known_composition_and_preserves_json_compatibility():
    payload = _payload("product-1", "promotion-1")

    assert isinstance(payload.config, dict)
    assert payload.config["pricing_mode"] == "product_promotion"
    assert payload.config["restrictions"]["flavor_count"] == 2
    assert payload.config["legacy_flag"] is True

    legacy = StrategicOfferCreate(
        code="LEGACY",
        title="Oferta antiga",
        product_id="product-1",
        price_original=Decimal("20.00"),
        price_promotional=Decimal("15.00"),
        config={"source": "legacy-client"},
    )
    assert legacy.config == {"source": "legacy-client"}


@pytest.mark.parametrize(
    "config",
    [
        {"pricing_mode": "product_promotion"},
        {"pricing_mode": "catalog", "product_promotion_id": "promotion-1"},
        {"restrictions": {"flavor_count": 4}},
        {"restrictions": {"size_ids": ["size-1", "size-1"]}},
    ],
)
def test_config_rejects_invalid_composition(config):
    with pytest.raises(ValidationError):
        StrategicOfferCreate(
            code="INVALID",
            title="Oferta inválida",
            product_id="product-1",
            price_original=Decimal("20.00"),
            price_promotional=Decimal("15.00"),
            config=config,
        )


def test_create_offer_persists_validated_config_for_same_tenant_product_promotion(db):
    campaign = _campaign(db)
    _product(db, "product-1", "tenant-1")
    _promotion(db, "promotion-1", "product-1", "tenant-1")

    offer = StrategicCampaignService(db, "tenant-1").add_offer(
        campaign.id,
        _payload("product-1", "promotion-1"),
    )

    assert offer.config["product_promotion_id"] == "promotion-1"
    assert offer.config["restrictions"]["option_ids"] == ["option-1"]
    assert offer.config["legacy_flag"] is True


@pytest.mark.parametrize(
    ("promotion_product_id", "promotion_tenant_id"),
    [
        ("product-2", "tenant-1"),
        ("product-1", "tenant-2"),
    ],
)
def test_create_offer_rejects_promotion_from_other_product_or_tenant(
    db,
    promotion_product_id,
    promotion_tenant_id,
):
    campaign = _campaign(db)
    _product(db, "product-1", "tenant-1")
    if promotion_product_id != "product-1":
        _product(db, promotion_product_id, promotion_tenant_id)
    _promotion(db, "promotion-1", promotion_product_id, promotion_tenant_id)

    with pytest.raises(DomainError) as error:
        StrategicCampaignService(db, "tenant-1").add_offer(
            campaign.id,
            _payload("product-1", "promotion-1"),
        )

    assert error.value.code == "StrategicOfferPromotionNotFound"
    assert db.query(StrategicOffer).count() == 0


def test_update_offer_cannot_bypass_promotion_ownership_validation(db):
    campaign = _campaign(db)
    _product(db, "product-1", "tenant-1")
    _product(db, "product-2", "tenant-1")
    _promotion(db, "promotion-1", "product-1", "tenant-1")
    _promotion(db, "promotion-2", "product-2", "tenant-1")
    service = StrategicCampaignService(db, "tenant-1")
    offer = service.add_offer(campaign.id, _payload("product-1", "promotion-1"))

    with pytest.raises(DomainError) as error:
        service.update_offer(
            offer.id,
            StrategicOfferUpdate(
                config={
                    "pricing_mode": "product_promotion",
                    "product_promotion_id": "promotion-2",
                },
            ),
        )

    assert error.value.code == "StrategicOfferPromotionNotFound"
    assert offer.config["product_promotion_id"] == "promotion-1"
