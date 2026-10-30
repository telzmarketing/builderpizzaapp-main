from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from backend.main import app
from backend.schemas.bi import BIKdsAnalyticsOut
from backend.services.business_intelligence_service import BusinessIntelligenceService


ROOT = Path(__file__).resolve().parents[1]


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self.rows


class _Db:
    def __init__(self, orders, units, attempts):
        self.rows = {"order": orders, "unit": units, "attempt": attempts}

    def query(self, model):
        name = model.__name__.lower()
        return _Query(self.rows["order" if name == "order" else "unit" if name == "productionunit" else "attempt"])


def _order(order_id, tenant_id="tenant-a", **timestamps):
    return SimpleNamespace(
        id=order_id,
        tenant_id=tenant_id,
        created_at=datetime(2026, 10, 20, 12, tzinfo=timezone.utc),
        status="delivered",
        **timestamps,
    )


def test_kds_analytics_is_registered_and_has_a_stable_contract():
    assert "/api/bi/kds-analytics" in {route.path for route in app.routes}
    source = (ROOT / "backend/routes/bi.py").read_text(encoding="utf-8")
    assert 'router.get("/kds-analytics", dependencies=' in source
    assert 'return ok(service.get_kds_analytics(**bounds))' in source


def test_kds_analytics_aggregates_persisted_flow_and_production_without_cross_tenant_data():
    order = _order(
        "order-a",
        paid_at=datetime(2026, 10, 20, 12, tzinfo=timezone.utc),
        preparation_started_at=datetime(2026, 10, 20, 12, 10, tzinfo=timezone.utc),
        ready_for_pickup_at=datetime(2026, 10, 20, 12, 35, tzinfo=timezone.utc),
        out_for_delivery_at=datetime(2026, 10, 20, 12, 45, tzinfo=timezone.utc),
        delivered_at=datetime(2026, 10, 20, 13, 15, tzinfo=timezone.utc),
    )
    foreign = _order("order-b", tenant_id="tenant-b")
    unit = SimpleNamespace(state="ready", tenant_id="tenant-a", created_at=order.created_at)
    attempt = SimpleNamespace(
        attempt_number=2,
        tenant_id="tenant-a",
        created_at=order.created_at,
        completed_at=datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc),
    )
    data = BusinessIntelligenceService(_Db([order], [unit], [attempt]), "tenant-a").get_kds_analytics(
        datetime(2026, 10, 1, tzinfo=timezone.utc),
        datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc),
        "30d",
        date(2026, 10, 1),
        date(2026, 10, 31),
    )

    validated = BIKdsAnalyticsOut.model_validate(data).model_dump()
    assert validated["orders"]["total"] == 1
    assert validated["orders"]["completed"] == 1
    assert validated["orders"]["stage_counts"]["delivered"] == 1
    assert validated["flow_minutes"]["payment_to_preparation"] == {"average": 10.0, "samples": 1}
    assert validated["flow_minutes"]["total"] == {"average": 75.0, "samples": 1}
    assert validated["production"]["units"] == 1
    assert validated["production"]["rework_attempts"] == 1
    assert "order-b" not in repr(validated)
    assert foreign.tenant_id == "tenant-b"  # fixture proves the service received only trusted rows
