from datetime import datetime, timezone
from types import SimpleNamespace

from backend.models.payment import PaymentStatus
from backend.services.finance_service import FinanceService


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def join(self, *args, **kwargs):
        return self

    def all(self):
        return self.rows


class _Db:
    def __init__(self, rows):
        self.rows = rows

    def query(self, *_args):
        return _Query(self.rows)


def test_sales_overview_reads_confirmed_payments_by_day_without_ledger_projection():
    first = SimpleNamespace(
        tenant_id="tenant-a",
        status=PaymentStatus.approved,
        amount=40.0,
        paid_at=datetime(2026, 11, 23, 12, tzinfo=timezone.utc),
        created_at=datetime(2026, 11, 23, 11, tzinfo=timezone.utc),
    )
    second = SimpleNamespace(
        tenant_id="tenant-a",
        status=PaymentStatus.paid,
        amount=25.5,
        paid_at=None,
        created_at=datetime(2026, 11, 24, 11, tzinfo=timezone.utc),
    )

    result = FinanceService(_Db([first, second]), "tenant-a").sales_overview()

    assert result["total_count"] == 2
    assert result["gross_amount"] == 65.5
    assert result["by_day"] == [
        {"date": first.paid_at.date(), "gross_amount": 40.0, "order_count": 1},
        {"date": second.created_at.date(), "gross_amount": 25.5, "order_count": 1},
    ]
