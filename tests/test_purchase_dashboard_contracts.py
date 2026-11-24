from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError

from backend.schemas.purchase_dashboard import PurchaseDashboardOut
from backend.services.purchase_dashboard_service import PurchaseDashboardService

def payload():
    return {
        "period": {"date_from": date(2026, 1, 1), "date_to": date(2026, 1, 31), "generated_at": "2026-01-31T12:00:00Z"},
        "requisitions": {"total": 1, "by_status": {"approved": 1}},
        "quotations": {"total": 1, "by_status": {"awarded": 1}},
        "orders": {"total": 1, "by_status": {"confirmed": 1}, "total_amount": "100.00"},
        "receipts": {"total": 1, "by_status": {"posted": 1}, "posted": 1, "quantity_received": "10", "quantity_rejected": "1"},
        "inventory": {"movement_count": 1, "quantity_in": "9", "received_value": "90.00"},
        "finance": {"obligation_count": 1, "total_amount": "100.00", "pending_amount": "100.00", "paid_amount": "0"},
        "alerts": {"overdue_quotations": 0, "overdue_orders": 0, "pending_requisitions": 0},
    }

def test_dashboard_contract_preserves_decimal_totals():
    result = PurchaseDashboardOut.model_validate(payload())
    assert result.orders.total_amount == Decimal("100.00")
    assert result.receipts.posted == 1

def test_dashboard_rejects_missing_sections():
    with pytest.raises(ValidationError):
        PurchaseDashboardOut.model_validate({"period": payload()["period"]})

def test_dashboard_period_rejects_inverted_range():
    with pytest.raises(ValueError):
        PurchaseDashboardService._bounds(date(2026, 2, 1), date(2026, 1, 1))

def test_dashboard_period_rejects_ranges_over_one_year():
    with pytest.raises(ValueError):
        PurchaseDashboardService._bounds(date(2025, 1, 1), date(2026, 1, 3))
