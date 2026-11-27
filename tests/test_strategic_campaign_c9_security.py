from decimal import Decimal

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main  # noqa: F401 - load the complete SQLAlchemy registry
from backend.core.exceptions import DomainError
from backend.database import Base
from backend.models.product import Product
from backend.models.product_promotion import ProductPromotion
from backend.models.strategic_campaign import (
    StrategicCampaign,
    StrategicCampaignStatus,
    StrategicCampaignVersion,
    StrategicOffer,
    StrategicOfferComponent,
)
from backend.routes import strategic_campaigns
from backend.schemas.order import CheckoutIn, DeliveryAddressIn
from backend.schemas.strategic_campaign import (
    StrategicCampaignUpdate,
    StrategicOfferCreate,
    StrategicOfferUpdate,
)
from backend.services.order_service import OrderService
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
            StrategicCampaignVersion.__table__,
        ],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def _campaign(db, tenant_id: str, *, suffix: str) -> StrategicCampaign:
    campaign = StrategicCampaign(
        id=f"campaign-{suffix}",
        tenant_id=tenant_id,
        name=f"Campanha {suffix}",
        commercial_name=f"Oferta {suffix}",
        slug="oferta-exclusiva",
        status=StrategicCampaignStatus.draft,
        visual_config={"hero": {"title": f"Hero {suffix}"}},
        commercial_config={"sales_mode": "immediate"},
        marketing_config={},
    )
    offer = StrategicOffer(
        id=f"offer-{suffix}",
        tenant_id=tenant_id,
        campaign_id=campaign.id,
        code=f"CODE-{suffix}",
        title=f"Oferta {suffix}",
        product_id=f"product-{suffix}",
        price_original=Decimal("50.00"),
        price_promotional=Decimal("39.90"),
        active=True,
        display_order=0,
        config={"restrictions": {"size_ids": [f"size-{suffix}"]}},
    )
    db.add_all([campaign, offer])
    db.commit()
    return campaign


def _closure_values(dependency) -> set[str]:
    return {
        cell.cell_contents
        for cell in dependency.__closure__ or ()
        if isinstance(cell.cell_contents, str)
    }


def test_tenant_cannot_read_update_or_publish_foreign_campaign(db):
    foreign = _campaign(db, "tenant-b", suffix="b")
    service = StrategicCampaignService(db, "tenant-a")

    for operation in (
        lambda: service._campaign(foreign.id),
        lambda: service.update(foreign.id, StrategicCampaignUpdate(name="Cross tenant")),
        lambda: service.publish(foreign.id),
    ):
        with pytest.raises(DomainError) as error:
            operation()
        assert error.value.code == "StrategicCampaignNotFound"


def test_public_snapshot_lookup_is_isolated_when_tenants_share_slug(db):
    campaign_a = _campaign(db, "tenant-a", suffix="a")
    campaign_b = _campaign(db, "tenant-b", suffix="b")

    StrategicCampaignService(db, "tenant-a").publish(campaign_a.id)
    StrategicCampaignService(db, "tenant-b").publish(campaign_b.id)

    public_a = StrategicCampaignService(db, "tenant-a").get_public("oferta-exclusiva")
    public_b = StrategicCampaignService(db, "tenant-b").get_public("oferta-exclusiva")

    assert public_a.id == campaign_a.id
    assert public_a.offers[0].id == "offer-a"
    assert public_b.id == campaign_b.id
    assert public_b.offers[0].id == "offer-b"


def test_every_administrative_route_has_view_or_edit_rbac_dependency():
    public_paths = {
        "/strategic-campaigns/public/{slug}",
        "/strategic-campaigns/public/offers/{offer_id}/configuration",
    }
    admin_routes = [
        route
        for route in strategic_campaigns.router.routes
        if isinstance(route, APIRoute) and route.path not in public_paths
    ]

    assert admin_routes
    for route in admin_routes:
        dependencies = {dependency.call for dependency in route.dependant.dependencies}
        assert dependencies & {strategic_campaigns.view, strategic_campaigns.edit, strategic_campaigns.publish}, (
            f"{','.join(sorted(route.methods))} {route.path} sem dependencia RBAC"
        )

    assert _closure_values(strategic_campaigns.view) == {"marketing", "view"}
    assert _closure_values(strategic_campaigns.edit) == {"marketing", "edit"}
    assert _closure_values(strategic_campaigns.publish) == {"marketing", "publish"}


def test_publish_route_requires_dedicated_sensitive_permission():
    publish_route = next(
        route
        for route in strategic_campaigns.router.routes
        if isinstance(route, APIRoute)
        and route.path == "/strategic-campaigns/{campaign_id}/publish"
    )
    dependency_values = {
        value
        for dependency in publish_route.dependant.dependencies
        for value in _closure_values(dependency.call)
    }

    assert dependency_values == {"marketing", "publish"}


def test_published_snapshot_remains_deeply_immutable_after_draft_changes(db):
    campaign = _campaign(db, "tenant-a", suffix="a")
    service = StrategicCampaignService(db, "tenant-a")
    version = service.publish(campaign.id)
    original_snapshot = version.snapshot

    service.update(
        campaign.id,
        StrategicCampaignUpdate(
            commercial_name="Rascunho alterado",
            visual_config={"hero": {"title": "Novo rascunho"}},
        ),
    )
    service.update_offer(
        "offer-a",
        # Updating nested JSON through the validated contract must not rewrite v1.
        StrategicOfferUpdate(
            title="Oferta do rascunho",
            config={"restrictions": {"size_ids": ["size-new"]}},
        ),
    )

    db.expire_all()
    stored = db.query(StrategicCampaignVersion).filter_by(id=version.id).one()
    public = service.get_public("oferta-exclusiva")

    assert stored.snapshot == original_snapshot
    assert stored.snapshot["campaign"]["visual_config"]["hero"]["title"] == "Hero a"
    assert stored.snapshot["offers"][0]["config"]["restrictions"]["size_ids"] == ["size-a"]
    assert public.commercial_name == "Oferta a"
    assert public.offers[0].title == "Oferta a"


def test_offer_rejects_inactive_product_promotion(db):
    campaign = _campaign(db, "tenant-a", suffix="a")
    db.add(
        Product(
            id="product-real",
            tenant_id="tenant-a",
            name="Produto real",
            description="Produto de teste",
            price=50,
            active=True,
        )
    )
    db.add(
        ProductPromotion(
            id="promotion-inactive",
            tenant_id="tenant-a",
            product_id="product-real",
            name="Promocao inativa",
            active=False,
        )
    )
    db.commit()

    with pytest.raises(DomainError) as error:
        StrategicCampaignService(db, "tenant-a").add_offer(
            campaign.id,
            StrategicOfferCreate(
                code="INACTIVE-PROMO",
                title="Oferta invalida",
                product_id="product-real",
                price_original=Decimal("50.00"),
                price_promotional=Decimal("39.90"),
                config={
                    "pricing_mode": "product_promotion",
                    "product_promotion_id": "promotion-inactive",
                },
            ),
        )

    assert error.value.code == "StrategicOfferPromotionNotFound"


def test_conventional_checkout_does_not_require_or_query_strategic_campaigns():
    class NoQueryDb:
        def query(self, *_args, **_kwargs):
            raise AssertionError("checkout convencional nao deve consultar campanha estrategica")

    payload = CheckoutIn(
        campaign_id="traffic-campaign-is-not-a-strategic-offer",
        items=[
            {
                "product_id": "product-1",
                "quantity": 1,
                "selected_size": "Unico",
                "final_price": 25,
            }
        ],
        delivery=DeliveryAddressIn(
            name="Cliente",
            phone="5511999999999",
            street="Rua Teste, 1",
            city="Sao Paulo",
        ),
        payment_method="pix",
    )
    service = OrderService(NoQueryDb())

    assert payload.strategic_offer_id is None
    assert service._resolve_strategic_context(payload) is None
    assert service._strategic_allows_closed_store(None) is False
    service._validate_strategic_commercial_rules(payload, None)
    service._assert_strategic_quote(None, 25.0, payload.items)
