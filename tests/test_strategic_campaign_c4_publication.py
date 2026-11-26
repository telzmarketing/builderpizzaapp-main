from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main  # noqa: F401
from backend.database import Base
from backend.models.strategic_campaign import (
    StrategicCampaign,
    StrategicCampaignStatus,
    StrategicCampaignVersion,
    StrategicOffer,
)
from backend.schemas.strategic_campaign import StrategicCampaignUpdate, StrategicOfferUpdate
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
            StrategicCampaign.__table__,
            StrategicOffer.__table__,
            StrategicCampaignVersion.__table__,
        ],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def _draft(db):
    campaign = StrategicCampaign(
        id="campaign-c4",
        tenant_id="tenant-1",
        name="Black Friday",
        commercial_name="Black Friday publicada",
        slug="black-friday",
        description="Primeira versão",
        status=StrategicCampaignStatus.draft,
        visual_config={"heroTitle": "Versão publicada"},
        commercial_config={"sales_mode": "immediate"},
        marketing_config={"planned_budget": 1000},
    )
    offer = StrategicOffer(
        id="offer-c4",
        tenant_id="tenant-1",
        campaign_id=campaign.id,
        code="BF-1",
        title="Oferta publicada",
        product_id="product-1",
        price_original=Decimal("50.00"),
        price_promotional=Decimal("39.90"),
        active=True,
        display_order=0,
        config={"source": "catalog"},
    )
    db.add_all([campaign, offer])
    db.commit()
    return campaign, offer


def test_public_api_reads_only_selected_published_snapshot(db):
    campaign, offer = _draft(db)
    service = StrategicCampaignService(db, "tenant-1")

    first = service.publish(campaign.id)
    assert first.version == 1
    assert first.snapshot["schema_version"] == 1

    service.update(
        campaign.id,
        StrategicCampaignUpdate(
            commercial_name="Rascunho alterado",
            description="Segunda versão ainda não publicada",
            slug="black-friday-next",
            visual_config={"heroTitle": "Rascunho"},
        ),
    )
    service.update_offer(
        offer.id,
        StrategicOfferUpdate(title="Oferta do rascunho", price_promotional=Decimal("29.90")),
    )

    public = service.get_public("black-friday")
    assert public.commercial_name == "Black Friday publicada"
    assert public.description == "Primeira versão"
    assert public.visual_config == {"heroTitle": "Versão publicada"}
    assert public.offers[0].title == "Oferta publicada"
    assert public.offers[0].price_promotional == Decimal("39.90")
    assert public.published_version == 1
    assert public.schema_version == 1


def test_republish_creates_new_immutable_version_and_moves_public_slug(db):
    campaign, offer = _draft(db)
    service = StrategicCampaignService(db, "tenant-1")
    first = service.publish(campaign.id)

    service.update(
        campaign.id,
        StrategicCampaignUpdate(slug="black-friday-2026", commercial_name="Versão 2"),
    )
    service.update_offer(offer.id, StrategicOfferUpdate(title="Oferta versão 2"))
    second = service.publish(campaign.id)

    assert second.version == 2
    assert second.id != first.id
    assert campaign.published_version == 2
    assert first.snapshot["campaign"]["commercial_name"] == "Black Friday publicada"
    assert first.snapshot["offers"][0]["title"] == "Oferta publicada"

    public = service.get_public("black-friday-2026")
    assert public.commercial_name == "Versão 2"
    assert public.offers[0].title == "Oferta versão 2"
    assert public.published_version == 2


def test_public_document_does_not_fall_back_to_mutable_campaign_or_offers(db):
    campaign, offer = _draft(db)
    service = StrategicCampaignService(db, "tenant-1")
    service.publish(campaign.id)

    campaign.commercial_name = "Alteração direta no rascunho"
    offer.title = "Alteração direta na oferta"
    db.commit()

    public = service.get_public("black-friday")
    assert public.commercial_name == "Black Friday publicada"
    assert public.offers[0].title == "Oferta publicada"
