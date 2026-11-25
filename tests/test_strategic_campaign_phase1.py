from decimal import Decimal
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.models.strategic_campaign import StrategicCampaignStatus
from backend.schemas.strategic_campaign import StrategicOfferCreate
from backend.schemas.order import CheckoutIn, DeliveryAddressIn
from backend.services.strategic_campaign_service import StrategicCampaignService
from backend.services.order_service import OrderService


def test_offer_requires_exactly_one_catalog_reference():
    with pytest.raises(ValidationError):
        StrategicOfferCreate(
            code="BLACK-001",
            title="Combo",
            product_id="product-1",
            kit_id="kit-1",
            price_original=Decimal("50.00"),
            price_promotional=Decimal("40.00"),
        )


def test_offer_rejects_promotional_price_above_original():
    with pytest.raises(ValidationError):
        StrategicOfferCreate(
            code="BLACK-001",
            title="Combo",
            product_id="product-1",
            price_original=Decimal("40.00"),
            price_promotional=Decimal("50.00"),
        )


def test_campaign_transition_is_fail_closed():
    with pytest.raises(Exception):
        StrategicCampaignService._assert_transition(
            StrategicCampaignStatus.ended,
            StrategicCampaignStatus.active,
        )


def test_campaign_transition_allows_draft_to_scheduled():
    StrategicCampaignService._assert_transition(
        StrategicCampaignStatus.draft,
        StrategicCampaignStatus.scheduled,
    )


def test_offer_period_must_be_ordered():
    with pytest.raises(ValidationError):
        StrategicOfferCreate(
            code="BLACK-001",
            title="Combo",
            product_id="product-1",
            price_original=Decimal("50.00"),
            price_promotional=Decimal("40.00"),
            sales_starts_at=datetime.now(timezone.utc),
            sales_ends_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )


def test_commercial_config_rejects_invalid_lead_time():
    from backend.schemas.strategic_campaign import StrategicCommercialConfig

    with pytest.raises(ValidationError):
        StrategicCommercialConfig(min_lead_minutes=-1)


def test_preorder_requires_scheduled_datetime():
    payload = CheckoutIn(
        items=[],
        delivery=DeliveryAddressIn(name="Cliente", phone="5511999999999", street="Rua", city="Sao Paulo"),
        payment_method="pix",
    )
    payload.items = []
    campaign = SimpleNamespace(commercial_config={"sales_mode": "preorder"})
    with pytest.raises(Exception, match="exige data"):
        OrderService._validate_strategic_commercial_rules(payload, (campaign, SimpleNamespace()))
