from types import SimpleNamespace as S
from unittest.mock import MagicMock

import pytest

from backend.core.exceptions import DomainError
from backend.schemas.order import CheckoutIn
from backend.services.delivery_service import DeliveryService
from backend.services.order_service import OrderService
from backend.services.shipping_service import ShippingService
from backend.services.store_operation_service import StoreOperationService


def test_final_checkout_geocodes_full_street_and_blocks_outside_radius_before_persisting(monkeypatch):
    db = MagicMock()
    service = OrderService.__new__(OrderService)
    service._db, service._tenant_context = db, None
    service._get_config = lambda: S()
    service._validate_item = lambda *_: (50, [], S(blocks_other_coupons=False, free_shipping=False), None, None)
    service._validate_inventory_items = lambda *_: None
    service._collect_promotion_gifts = lambda *_: []
    monkeypatch.setattr(StoreOperationService, "validate_order_allowed", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ShippingService, "get_config", lambda _: S(delivery_enabled=True, pickup_enabled=True, store_lat=0, store_lng=0, max_delivery_distance=3))
    monkeypatch.setattr(ShippingService, "_publish", lambda *_args, **_kwargs: None)
    geocode = MagicMock(return_value={"lat": 0, "lng": 1})
    monkeypatch.setattr(DeliveryService, "geocode_address", geocode)
    payload = CheckoutIn(items=[{"product_id": "pizza", "quantity": 1, "selected_size": "Grande", "flavors": [], "final_price": 50}], delivery={"name": "Cliente", "phone": "11999999999", "street": "Rua Fora do Raio, 120", "city": "São Paulo", "zip_code": "01001000"})
    with pytest.raises(DomainError, match="raio de entrega"):
        service.create_from_checkout(payload)
    assert "Rua Fora do Raio, 120" in geocode.call_args.args[0]
    db.add.assert_not_called()
    db.commit.assert_not_called()
