from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.tenant_context import TenantContext, TenantSource
from backend.database import Base
from backend.main import app
from backend.models.delivery import (
    Delivery,
    DeliveryPerson,
    DeliveryPersonStatus,
    DeliveryStatus,
)
from backend.models.order import Order, OrderStatus
from backend.models.tenant import Tenant
from backend.schemas.kds import KdsOverviewOut
from backend.services.kds_service import KdsService


ROOT = Path(__file__).resolve().parents[1]


def _context(tenant_id: str) -> TenantContext:
    return TenantContext(tenant_id=tenant_id, source=TenantSource.JOB)


def _order(
    order_id: str,
    tenant_id: str,
    status: OrderStatus,
    created_at: datetime,
    **timestamps,
) -> Order:
    return Order(
        id=order_id,
        tenant_id=tenant_id,
        order_code=order_id,
        status=status,
        fulfillment_type="delivery",
        sales_channel="delivery",
        subtotal=50,
        total=50,
        created_at=created_at,
        updated_at=created_at,
        delivery_name="DADO PESSOAL",
        delivery_phone="11999999999",
        delivery_street="RUA PRIVADA",
        notes="OBSERVACAO PRIVADA",
        **timestamps,
    )


def test_overview_is_tenant_scoped_counts_stages_and_exposes_bounded_contract():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__,
        Order.__table__,
        DeliveryPerson.__table__,
        Delivery.__table__,
    ])
    db = sessionmaker(bind=engine)()
    now = datetime(2026, 9, 29, 18, 0, tzinfo=timezone.utc)
    try:
        db.add_all([
            Tenant(id="tenant-a", slug="tenant-a", name="Loja A"),
            Tenant(id="tenant-b", slug="tenant-b", name="Loja B", is_legacy=True),
            DeliveryPerson(
                id="driver-available", tenant_id="tenant-a", name="Ana",
                phone="11900000001", status=DeliveryPersonStatus.available,
            ),
            DeliveryPerson(
                id="driver-busy", tenant_id="tenant-a", name="Bruno",
                phone="11900000002", status=DeliveryPersonStatus.busy,
            ),
            DeliveryPerson(
                id="driver-offline", tenant_id="tenant-a", name="Caio",
                phone="11900000003", status=DeliveryPersonStatus.offline,
            ),
            DeliveryPerson(
                id="driver-other-tenant", tenant_id="tenant-b", name="Intruso",
                phone="11900000004", status=DeliveryPersonStatus.available,
            ),
            _order(
                "waiting", "tenant-a", OrderStatus.paid,
                now - timedelta(minutes=25), paid_at=now - timedelta(minutes=24),
            ),
            _order(
                "preparing", "tenant-a", OrderStatus.preparing,
                now - timedelta(minutes=20),
                preparation_started_at=now - timedelta(minutes=18),
            ),
            _order(
                "ready", "tenant-a", OrderStatus.ready_for_pickup,
                now - timedelta(minutes=15),
                ready_for_pickup_at=now - timedelta(minutes=5),
            ),
            _order(
                "assigned", "tenant-a", OrderStatus.ready_for_pickup,
                now - timedelta(minutes=14),
                ready_for_pickup_at=now - timedelta(minutes=4),
            ),
            _order(
                "route", "tenant-a", OrderStatus.on_the_way,
                now - timedelta(minutes=13),
                out_for_delivery_at=now - timedelta(minutes=2),
            ),
            _order(
                "other-tenant", "tenant-b", OrderStatus.preparing,
                now - timedelta(minutes=30),
            ),
        ])
        db.flush()
        db.add_all([
            Delivery(
                id="delivery-assigned", tenant_id="tenant-a", order_id="assigned",
                delivery_person_id="driver-busy", status=DeliveryStatus.assigned,
                assigned_at=now - timedelta(minutes=3),
            ),
            Delivery(
                id="delivery-route", tenant_id="tenant-a", order_id="route",
                delivery_person_id="driver-busy", status=DeliveryStatus.on_the_way,
                assigned_at=now - timedelta(minutes=6),
                picked_up_at=now - timedelta(minutes=2),
            ),
        ])
        db.commit()

        payload = KdsOverviewOut.model_validate(
            KdsService(db, _context("tenant-a")).overview()
        ).model_dump()

        assert payload["counters"] == {
            "waiting_kitchen": 1,
            "preparing": 1,
            "ready_unassigned": 1,
            "assigned_waiting_departure": 1,
            "in_route": 1,
            "drivers_available": 1,
            "drivers_busy": 1,
        }
        assert [row["id"] for row in payload["orders"]] == [
            "waiting", "preparing", "ready", "assigned", "route",
        ]
        by_id = {row["id"]: row for row in payload["orders"]}
        assert payload["generated_at"].tzinfo == timezone.utc
        assert by_id["waiting"]["created_at"].tzinfo == timezone.utc
        assert by_id["waiting"]["status_started_at"] == now - timedelta(minutes=24)
        assert by_id["assigned"]["stage"] == "assigned_waiting_departure"
        assert by_id["assigned"]["status_started_at"] == now - timedelta(minutes=3)
        assert by_id["assigned"]["delivery"] == {
            "status": "assigned",
            "driver_name": "Bruno",
        }
        assert by_id["route"]["stage"] == "in_route"
        assert set(by_id["ready"]) == {
            "id", "order_code", "stage", "status", "fulfillment_type",
            "created_at", "status_started_at", "delivery",
        }
        serialized = repr(payload)
        assert "other-tenant" not in serialized
        assert "DADO PESSOAL" not in serialized
        assert "11999999999" not in serialized
        assert "RUA PRIVADA" not in serialized
        assert "OBSERVACAO PRIVADA" not in serialized
    finally:
        db.close()


def test_overview_route_uses_orders_view_permission_and_is_registered():
    paths = {route.path for route in app.routes}
    assert "/api/kds/overview" in paths

    source = (ROOT / "backend/routes/kds.py").read_text(encoding="utf-8")
    overview_route = source[source.index('@router.get("/overview"'):source.index('@router.get("/kitchen/orders"')]
    assert 'require_rbac_permission("pedidos", "view")' in overview_route
    assert "KdsOverviewOut.model_validate" in overview_route


def test_picked_up_delivery_is_no_longer_counted_as_waiting_departure():
    service = KdsService(object(), _context("tenant-a"))
    order = SimpleNamespace(status=OrderStatus.ready_for_pickup)
    delivery = SimpleNamespace(status=DeliveryStatus.picked_up)

    assert service._overview_stage(order, delivery) == "in_route"
