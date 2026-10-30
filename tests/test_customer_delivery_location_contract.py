from pathlib import Path


ROUTE = Path("backend/routes/delivery.py")
SERVICE = Path("backend/services/delivery_service.py")
CLIENT_API = Path("client/lib/api.ts")
TRACKING_PAGE = Path("client/pages/OrderTracking.tsx")


def test_customer_location_route_is_authenticated_and_customer_scoped():
    route = ROUTE.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")

    assert '@router.get("/order/{order_id}/location")' in route
    assert "authenticate_customer_token(" in route
    assert "expected_tenant_id=tenant_context.tenant_id" in route
    assert "service.get_customer_location(order_id, customer.id)" in route
    assert "Order.customer_id == customer_id" in service
    assert "DeliveryStatus.picked_up" in service
    assert "CUSTOMER_LOCATION_MAX_AGE_SECONDS = 120" in service
    assert '"delivery_person_id"' not in service[service.index("def get_customer_location"):service.index("def get_customer_location") + 2500]


def test_tracking_uses_official_api_and_map_link_with_safe_states():
    api = CLIENT_API.read_text(encoding="utf-8")
    page = TRACKING_PAGE.read_text(encoding="utf-8")

    assert "getDeliveryLocation" in api
    assert "/delivery/order/${encodeURIComponent(id)}/location" in api
    assert "ordersApi.getDeliveryLocation(orderId)" in page
    assert "setInterval(() => void fetchDeliveryLocation(), 10_000)" in page
    assert "!deliveryLocation?.available" in page
    assert "https://www.google.com/maps/search/?api=1&query=" in page
