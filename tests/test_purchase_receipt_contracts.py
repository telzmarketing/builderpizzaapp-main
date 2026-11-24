from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError

from backend.schemas.purchase_receipt import PurchaseReceiptCreate

def line(**overrides):
    data = {"purchase_item_id": "purchase-item-1", "item_id": "item-1", "location_id": "loc-1", "quantity_received": "10", "quantity_rejected": "2", "unit_cost": "3.50"}
    data.update(overrides)
    return data

def test_receipt_schema_accepts_divergence_and_lot():
    body = PurchaseReceiptCreate(purchase_id="purchase-1", items=[line(lot_code="LOT-1", manufactured_on=date(2026, 1, 1), expires_on=date(2027, 1, 1))])
    assert body.items[0].quantity_received == Decimal("10")

def test_receipt_schema_requires_purchase_line_and_quality_policy():
    body = PurchaseReceiptCreate(purchase_id="purchase-1", items=[line(quality_status="quarantine", temperature_c="4.50")])
    assert body.items[0].quality_status == "quarantine"

@pytest.mark.parametrize("overrides", [{"quantity_received": "0"}, {"quantity_rejected": "11"}, {"manufactured_on": date(2027, 1, 1), "expires_on": date(2026, 1, 1)}])
def test_receipt_schema_rejects_invalid_quantities_and_dates(overrides):
    with pytest.raises(ValidationError):
        PurchaseReceiptCreate(purchase_id="purchase-1", items=[line(**overrides)])
