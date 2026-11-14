from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Product has a relationship declared against OrderItemFlavor; importing the
# owning model keeps SQLAlchemy's registry complete for this focused unit test.
import backend.models.order  # noqa: F401,E402
from backend.schemas.promotion_landing_page import PromotionLandingPageCreate
from backend.services import promotion_landing_service as landing_service_module
from backend.services.promotion_landing_service import (
    PromotionLandingRuleError,
    PromotionLandingService,
)


def _service():
    service = object.__new__(PromotionLandingService)
    service._db = MagicMock()
    service._tenant_context = None
    service._tenant_enabled = False
    return service


def test_product_landing_create_keeps_promotion_optional_and_reuses_media_contract(monkeypatch):
    payload = PromotionLandingPageCreate(
        product_id="product-1",
        landing_type="product",
        title="Pizza da casa",
        image_url="/uploads/main.jpg",
        image_url_2="/uploads/second.jpg",
        video_url="/uploads/hero.mp4",
    )
    assert payload.promotion_id is None
    assert payload.landing_type == "product"

    service = _service()
    class FakeLanding:
        def __init__(self, **values):
            self.__dict__.update(values)

    monkeypatch.setattr(landing_service_module, "PromotionLandingPage", FakeLanding)
    service._validate_product = MagicMock(return_value=SimpleNamespace(name="Pizza da casa"))
    service.get_by_product = MagicMock(return_value=None)
    service._unique_slug = MagicMock(return_value="pizza-da-casa")
    service._own = lambda landing: landing

    landing = service.create(payload.model_dump())

    assert isinstance(landing, FakeLanding)
    assert landing.landing_type == "product"
    assert landing.promotion_id is None
    assert landing.image_url_2 == "/uploads/second.jpg"
    assert landing.video_url == "/uploads/hero.mp4"


def test_only_one_independent_landing_is_allowed_per_product():
    service = _service()
    service._validate_product = MagicMock(return_value=SimpleNamespace(name="Pizza da casa"))
    service.get_active_product_landing = MagicMock(return_value=object())

    with pytest.raises(PromotionLandingRuleError) as error:
        service.create({
            "product_id": "product-1",
            "landing_type": "product",
            "title": "Outra página",
        })

    assert error.value.code == "ProductLandingAlreadyExists"


def test_landing_decision_prefers_active_promotion_before_independent_page():
    service = _service()
    independent = SimpleNamespace(landing_type="product")
    promotional = SimpleNamespace(landing_type="promotion")
    service.get_active_product_landing = MagicMock(return_value=independent)
    service.active_promotion_landing_for_product = MagicMock(return_value=promotional)

    result = service.active_landing_for_product(SimpleNamespace(id="product-1"))

    assert result is promotional
    service.get_active_product_landing.assert_not_called()


def test_landing_decision_falls_back_to_independent_page_without_active_promotion():
    service = _service()
    independent = SimpleNamespace(landing_type="product")
    service.active_promotion_landing_for_product = MagicMock(return_value=None)
    service.get_active_product_landing = MagicMock(return_value=independent)

    result = service.active_landing_for_product(SimpleNamespace(id="product-1"))

    assert result is independent
    service.get_active_product_landing.assert_called_once_with("product-1")


def test_promotion_create_without_promotion_id_is_rejected():
    service = _service()

    with pytest.raises(PromotionLandingRuleError) as error:
        service.create({
            "product_id": "product-1",
            "landing_type": "promotion",
            "title": "Oferta",
        })

    assert error.value.code == "PromotionRequired"
