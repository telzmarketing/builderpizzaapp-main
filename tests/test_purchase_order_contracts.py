from backend.schemas.inventory import InventoryPurchaseIn


def test_purchase_order_version_is_optional_for_legacy_payloads():
    payload = InventoryPurchaseIn(status="draft", items=[])
    assert payload.expected_version is None


def test_purchase_order_version_accepts_positive_value():
    payload = InventoryPurchaseIn(status="draft", expected_version=3, items=[])
    assert payload.expected_version == 3
