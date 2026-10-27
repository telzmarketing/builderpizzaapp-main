from pathlib import Path
from types import SimpleNamespace

from backend.models.order import Order
from backend.services.delivery_service import _driver_delivery_earning_amount
from backend.services.order_service import _driver_delivery_fee_snapshot


def test_distance_freight_snapshot_keeps_gross_value_before_customer_discount():
    shipping_result = SimpleNamespace(shipping_type="by_distance", shipping_price=12.345)

    assert _driver_delivery_fee_snapshot(
        shipping_result,
        is_pickup=False,
        sales_channel="delivery",
    ) == 12.35


def test_pickup_does_not_get_driver_fee_snapshot():
    distance_result = SimpleNamespace(shipping_type="by_distance", shipping_price=12.0)

    assert _driver_delivery_fee_snapshot(distance_result, is_pickup=True, sales_channel="delivery") is None


def test_dine_in_does_not_get_driver_fee_snapshot():
    distance_result = SimpleNamespace(shipping_type="by_distance", shipping_price=12.0)

    assert _driver_delivery_fee_snapshot(distance_result, is_pickup=False, sales_channel="dine_in") is None


def test_non_distance_freight_type_does_not_get_driver_fee_snapshot():
    fixed_result = SimpleNamespace(shipping_type="fixed", shipping_price=8.0)

    assert _driver_delivery_fee_snapshot(fixed_result, is_pickup=False, sales_channel="delivery") is None


def test_distance_order_snapshot_takes_precedence_over_changed_logistics_rate():
    order = SimpleNamespace(driver_delivery_fee=12.5)

    assert _driver_delivery_earning_amount(order, 7.0) == 12.5


def test_zero_distance_snapshot_preserves_free_freight_and_does_not_fallback():
    order = SimpleNamespace(driver_delivery_fee=0.0)

    assert _driver_delivery_earning_amount(order, 7.0) == 0.0


def test_legacy_order_uses_logistics_rate():
    order = SimpleNamespace(driver_delivery_fee=None)

    assert _driver_delivery_earning_amount(order, 7.0) == 7.0


def test_order_model_has_nullable_driver_fee_snapshot():
    assert Order.__table__.c.driver_delivery_fee.nullable is True


def test_driver_fee_migration_follows_current_project_head():
    migration = Path("backend/migrations/versions/20261026_order_driver_delivery_fee.py").read_text(encoding="utf-8")

    assert 'down_revision = "20261026_product_crust_visibility"' in migration
    assert 'sa.Column("driver_delivery_fee", sa.Float(), nullable=True)' in migration
