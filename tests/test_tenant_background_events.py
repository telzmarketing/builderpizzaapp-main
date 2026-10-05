from pathlib import Path


EVENTS = Path("backend/core/events.py")
MAIN = Path("backend/main.py")
PAYMENTS = Path("backend/services/payment_service.py")
ORDERS = Path("backend/services/order_service.py")
INVENTORY = Path("backend/services/inventory_service.py")


def test_finance_event_handlers_use_event_tenant() -> None:
    source = MAIN.read_text(encoding="utf-8")

    assert "def _event_tenant_id(event)" in source
    assert "TENANT_BACKGROUND_CONTEXT_ENABLED" in source
    assert "MULTI_TENANT_WAVE7_ORM_ENABLED" in source
    assert "def _finance_event_service(db, event)" in source
    assert "trusted_process_context(tenant_id, source=TenantSource.JOB)" in source
    assert "_finance_event_service(db, event).sync_payment_confirmed" in source
    assert "_finance_event_service(db, event).sync_payment_reversed" in source
    assert "_finance_event_service(db, event).sync_purchase_confirmed" in source
    assert "FinanceService(db).sync_payment_confirmed" not in source
    assert "FinanceService(db).sync_payment_reversed" not in source
    assert "FinanceService(db).sync_purchase_confirmed" not in source


def test_payment_and_inventory_events_carry_tenant_id() -> None:
    events = EVENTS.read_text(encoding="utf-8")
    payments = PAYMENTS.read_text(encoding="utf-8")
    orders = ORDERS.read_text(encoding="utf-8")
    inventory = INVENTORY.read_text(encoding="utf-8")

    for event_name in (
        "PaymentCreated",
        "PaymentConfirmed",
        "PaymentReversed",
        "PaymentFailed",
        "InventoryPurchaseConfirmed",
    ):
        assert f"class {event_name}(DomainEvent)" in events
    assert events.count("tenant_id: str | None = None") >= 8
    assert "tenant_id=payment.tenant_id" in payments
    assert "tenant_id=payment.tenant_id" in orders
    assert "tenant_id=purchase.tenant_id" in inventory


def test_inventory_side_effects_are_tenant_scoped() -> None:
    payments = PAYMENTS.read_text(encoding="utf-8")
    orders = ORDERS.read_text(encoding="utf-8")

    assert "InventoryService(self._db).consume_order_sale" not in payments
    assert "InventoryService(self._db).reverse_order_sale" not in payments
    assert "InventoryService(self._db).consume_order_sale" not in orders
    assert "InventoryService(self._db).reverse_order_sale" not in orders
    assert "trusted_process_context(order.tenant_id, source=TenantSource.WEBHOOK)" in payments
    assert "InventoryService(self._db, order.tenant_id, self._tenant_context).consume_order_sale" in orders
