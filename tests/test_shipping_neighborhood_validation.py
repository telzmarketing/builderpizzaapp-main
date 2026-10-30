from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.models.shipping_v2 import FreightTypeConfig, ShippingExtraRule, ShippingNeighborhood, ShippingPromotion
from backend.schemas.shipping_v2 import ShippingCalculateIn, ShippingNeighborhoodCreate, ShippingNeighborhoodUpdate
from backend.services.shipping_service import ShippingService, _normalize_area_name


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *conditions):
        return self

    def order_by(self, *ordering):
        return self

    def all(self):
        return list(self.rows)


def _shipping_service(*, neighborhood, freight_type="by_neighborhood"):
    service = ShippingService.__new__(ShippingService)
    service._db = SimpleNamespace()
    service._tenant_context = None
    service._tenant_enabled = False

    config = SimpleNamespace(
        delivery_enabled=True,
        pickup_enabled=False,
        pickup_message="Retire em nossa loja",
        min_order_value=0.0,
        default_estimated_time=45,
        max_delivery_distance=3.0,
        default_base_fee=7.0,
        unavailable_message="Região não atendida.",
        store_lat=None,
        store_lng=None,
    )
    type_config = SimpleNamespace(
        freight_type=freight_type,
        active=True,
        priority=10,
    )

    def query(model):
        if model is ShippingExtraRule or model is ShippingPromotion:
            return _Query([])
        if model is FreightTypeConfig:
            return _Query([type_config])
        if model is ShippingNeighborhood:
            return _Query([neighborhood])
        raise AssertionError(f"modelo não previsto no teste: {model}")

    service._query = query
    service.get_config = lambda: config
    service._resolve_distance_km = lambda payload, cfg: None
    service._ensure_type_configs = lambda: None
    service._apply_extra_surcharges = lambda result, payload, cfg, now: result
    service._publish = lambda result, payload, order_id: None
    return service


def test_neighborhood_create_requires_non_empty_name_and_city_and_non_negative_value():
    valid = ShippingNeighborhoodCreate(
        name="  Jardim América ",
        city=" São Paulo ",
        shipping_value=12.5,
    )

    assert valid.name == "Jardim América"
    assert valid.city == "São Paulo"

    with pytest.raises(ValidationError):
        ShippingNeighborhoodCreate(name="   ", city="São Paulo")
    with pytest.raises(ValidationError):
        ShippingNeighborhoodCreate(name="Centro", city="   ")
    with pytest.raises(ValidationError):
        ShippingNeighborhoodCreate(name="Centro", city="São Paulo", shipping_value=-0.01)


def test_neighborhood_update_rejects_blank_area_parts_and_negative_value():
    with pytest.raises(ValidationError):
        ShippingNeighborhoodUpdate(city=" ")
    with pytest.raises(ValidationError):
        ShippingNeighborhoodUpdate(name="Centro", shipping_value=-1)


def test_area_normalization_ignores_accents_case_and_extra_spaces():
    assert _normalize_area_name("  São  José ") == "sao jose"
    assert _normalize_area_name("SAO JOSE") == "sao jose"


def test_calculation_requires_matching_neighborhood_and_city_before_returning_price():
    neighborhood = SimpleNamespace(
        name="Jardim América",
        city="São Paulo",
        active=True,
        priority=0,
        min_order_value=0.0,
        is_free=False,
        shipping_value=12.5,
        estimated_time_min=45,
        notes="",
    )
    service = _shipping_service(neighborhood=neighborhood)

    matched = service.calculate(
        ShippingCalculateIn(neighborhood="JARDIM AMERICA", city="sao paulo", order_subtotal=50)
    )
    assert matched.shipping_type == "by_neighborhood"
    assert matched.shipping_price == 12.5

    wrong_city = service.calculate(
        ShippingCalculateIn(neighborhood="JARDIM AMERICA", city="Campinas", order_subtotal=50)
    )
    assert wrong_city.shipping_type == "unavailable"
    assert wrong_city.available is False
    assert wrong_city.shipping_price == 0.0


def test_calculation_does_not_match_neighborhood_without_city():
    neighborhood = SimpleNamespace(
        name="Centro",
        city="São Paulo",
        active=True,
        priority=0,
        min_order_value=0.0,
        is_free=False,
        shipping_value=9.0,
        estimated_time_min=45,
        notes="",
    )
    service = _shipping_service(neighborhood=neighborhood)

    result = service.calculate(ShippingCalculateIn(neighborhood="Centro", order_subtotal=50))

    assert result.shipping_type == "unavailable"
    assert result.available is False
