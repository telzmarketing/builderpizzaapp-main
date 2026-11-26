from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Loads the complete model registry before SQLAlchemy configures relationships.
import backend.main  # noqa: F401
from backend.core.exceptions import DomainError
from backend.database import Base
from backend.models.strategic_campaign import (
    StrategicCampaign,
    StrategicCampaignStatus,
    StrategicCampaignVersion,
    StrategicOffer,
)
from backend.schemas.strategic_campaign import (
    StrategicCampaignDuplicate,
    StrategicOfferDuplicate,
    StrategicOfferReorder,
)
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


def _campaign(db, campaign_id="campaign-1", tenant_id="tenant-1", *, published_version=None):
    campaign = StrategicCampaign(
        id=campaign_id,
        tenant_id=tenant_id,
        name="Black Friday",
        commercial_name="Ofertas Black Friday",
        slug=f"black-friday-{campaign_id}",
        description="Campanha",
        status=StrategicCampaignStatus.active if published_version else StrategicCampaignStatus.draft,
        visual_config={"theme": {"primary": "#000000"}},
        commercial_config={"sales_mode": "immediate"},
        marketing_config={"planned_budget": 1000},
        published_version=published_version,
    )
    db.add(campaign)
    db.commit()
    return campaign


def _offer(
    db,
    campaign,
    offer_id="offer-1",
    *,
    code="OFFER-1",
    display_order=0,
    archived_at=None,
):
    offer = StrategicOffer(
        id=offer_id,
        tenant_id=campaign.tenant_id,
        campaign_id=campaign.id,
        code=code,
        title=f"Oferta {code}",
        product_id="product-1",
        price_original=Decimal("50.00"),
        price_promotional=Decimal("39.90"),
        active=archived_at is None,
        display_order=display_order,
        config={"source": "catalog"},
        archived_at=archived_at,
    )
    db.add(offer)
    db.commit()
    return offer


def test_duplicate_campaign_creates_draft_without_versions_and_skips_archived_offers(db):
    source = _campaign(db, published_version=1)
    active_offer = _offer(db, source)
    archived_offer = _offer(db, source, "offer-archived", code="OLD", display_order=1)
    archived_offer.active = False
    from datetime import datetime, timezone
    archived_offer.archived_at = datetime.now(timezone.utc)
    db.add(StrategicCampaignVersion(
        id="version-1",
        tenant_id=source.tenant_id,
        campaign_id=source.id,
        version=1,
        snapshot={
            "schema_version": 1,
            "campaign": {
                "id": source.id,
                "name": source.name,
                "slug": source.slug,
                "published_version": 1,
            },
            "offers": [],
        },
    ))
    db.commit()

    duplicated = StrategicCampaignService(db, "tenant-1").duplicate_campaign(
        source.id,
        StrategicCampaignDuplicate(),
    )

    assert duplicated.id != source.id
    assert duplicated.status == StrategicCampaignStatus.draft
    assert duplicated.published_version is None
    assert duplicated.slug == f"{source.slug}-copy"
    assert duplicated.visual_config == source.visual_config
    assert duplicated.visual_config is not source.visual_config
    assert [(offer.code, offer.id != active_offer.id) for offer in duplicated.offers] == [("OFFER-1", True)]
    assert db.query(StrategicCampaignVersion).filter_by(campaign_id=duplicated.id).count() == 0


def test_duplicate_offer_appends_copy_and_preserves_tenant_scope(db):
    campaign = _campaign(db)
    source = _offer(db, campaign)
    _offer(db, campaign, "offer-2", code="OFFER-2", display_order=4)

    duplicated = StrategicCampaignService(db, "tenant-1").duplicate_offer(
        source.id,
        StrategicOfferDuplicate(),
    )

    assert duplicated.id != source.id
    assert duplicated.campaign_id == campaign.id
    assert duplicated.tenant_id == "tenant-1"
    assert duplicated.code == "OFFER-1-copy"
    assert duplicated.title.endswith("(cópia)")
    assert duplicated.display_order == 5
    assert duplicated.archived_at is None

    other_campaign = _campaign(db, "campaign-2", "tenant-2")
    other_offer = _offer(db, other_campaign, "offer-other", code="OTHER")
    with pytest.raises(DomainError) as error:
        StrategicCampaignService(db, "tenant-1").duplicate_offer(other_offer.id, StrategicOfferDuplicate())
    assert error.value.code == "StrategicOfferNotFound"


def test_reorder_requires_exact_non_archived_offer_set(db):
    campaign = _campaign(db)
    first = _offer(db, campaign)
    second = _offer(db, campaign, "offer-2", code="OFFER-2", display_order=1)

    ordered = StrategicCampaignService(db, "tenant-1").reorder_offers(
        campaign.id,
        StrategicOfferReorder(offer_ids=[second.id, first.id]),
    )
    assert [(offer.id, offer.display_order) for offer in ordered] == [(second.id, 0), (first.id, 1)]

    with pytest.raises(DomainError) as error:
        StrategicCampaignService(db, "tenant-1").reorder_offers(
            campaign.id,
            StrategicOfferReorder(offer_ids=[first.id]),
        )
    assert error.value.code == "InvalidStrategicOfferOrder"


def test_reorder_schema_rejects_duplicate_ids():
    with pytest.raises(ValidationError):
        StrategicOfferReorder(offer_ids=["offer-1", "offer-1"])


def test_archive_offer_is_soft_delete_and_is_idempotency_fail_closed(db):
    campaign = _campaign(db)
    offer = _offer(db, campaign)
    service = StrategicCampaignService(db, "tenant-1")

    archived = service.archive_offer(offer.id)

    assert archived.active is False
    assert archived.archived_at is not None
    assert db.query(StrategicOffer).filter_by(id=offer.id).count() == 1
    with pytest.raises(DomainError) as error:
        service.archive_offer(offer.id)
    assert error.value.code == "StrategicOfferArchived"


def test_offer_mutations_prepare_next_draft_after_campaign_publication(db):
    campaign = _campaign(db, published_version=1)
    offer = _offer(db, campaign)
    service = StrategicCampaignService(db, "tenant-1")

    duplicated = service.duplicate_offer(offer.id, StrategicOfferDuplicate())
    archived = service.archive_offer(offer.id)

    assert duplicated.campaign_id == campaign.id
    assert archived.archived_at is not None
