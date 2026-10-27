from datetime import datetime, timedelta, timezone

from fastapi.encoders import jsonable_encoder
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.main import app  # noqa: F401 - register all related ORM models
from backend.database import Base
from backend.models.delivery import Delivery, DeliveryPerson, DeliveryStatus
from backend.models.order import Order
from backend.models.tenant import Tenant
from backend.routes.delivery import _driver_delivery_payload
from backend.services.delivery_service import DeliveryService


def test_driver_payload_preserves_public_order_code_and_legacy_null():
    for public_code in ("K5M4", None):
        order = Order(id="order-d5", order_code=public_code, tenant_id="tenant-a")
        delivery = Delivery(id="delivery", order=order, order_id=order.id, tenant_id="tenant-a")
        assert _driver_delivery_payload(delivery)["order"]["order_code"] == public_code


def test_delivery_identity_is_tenant_scoped_and_does_not_add_queries(monkeypatch):
    monkeypatch.setattr("backend.services.delivery_service.wave7_orm_enabled", lambda: False)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Order.__table__, DeliveryPerson.__table__, Delivery.__table__,
    ])
    now = datetime.now(timezone.utc)
    with sessionmaker(bind=engine)() as db:
        db.add_all([
            Tenant(id="tenant-a", slug="tenant-a", name="A"),
            # SQLite treats the PostgreSQL partial legacy index as full unique.
            Tenant(id="tenant-b", slug="tenant-b", name="B", is_legacy=True),
            Order(id="order-d5", order_code="K5M4", tenant_id="tenant-a", subtotal=10, total=10),
            Order(id="foreign", order_code="PRIVATE", tenant_id="tenant-b", subtotal=10, total=10),
            Delivery(id="d1", order_id="order-d5", tenant_id="tenant-a", status=DeliveryStatus.assigned,
                     problem_report="Atraso", assigned_at=now - timedelta(hours=2), estimated_minutes=20),
            Delivery(id="d2", order_id="foreign", tenant_id="tenant-b", status=DeliveryStatus.assigned),
            Delivery(id="invalid-link", order_id="foreign", tenant_id="tenant-a", status=DeliveryStatus.assigned),
        ])
        db.commit()
        db.expunge_all()
        queries = []
        event.listen(engine, "before_cursor_execute", lambda *_args: queries.append(_args[2]))
        service = DeliveryService(db, tenant_id="tenant-a")
        rows = service.list_active()
        payload = jsonable_encoder(rows)
        assert len(queries) == 1
        assert {row["id"] for row in payload} == {"d1", "invalid-link"}
        by_id = {row["id"]: row for row in payload}
        assert by_id["d1"]["order"]["order_code"] == "K5M4"
        assert "delivery_name" not in by_id["d1"]["order"]
        assert by_id["invalid-link"]["order"] is None
        assert "PRIVATE" not in str(payload)
        alerts = service.get_alerts()
        assert {alert["order_code"] for alert in alerts} == {"K5M4"}
    engine.dispose()
