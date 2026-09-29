from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.tenant_context import TenantContext, TenantSource
from backend.database import Base
from backend.main import app
from backend.models.delivery import Delivery, DeliveryPerson, DeliveryStatus
from backend.models.order import Order, OrderItem, OrderStatus
from backend.models.order_board import OrderBoardActivation, OrderBoardDevice, OrderBoardSetting
from backend.models.platform_saas import TenantProfile
from backend.models.product import Product
from backend.models.tenant import Tenant
from backend.schemas.order_board import OrderBoardSettingsIn
from backend.services.order_board_service import (
    OrderBoardForbidden,
    OrderBoardNotFound,
    OrderBoardService,
    OrderBoardUnauthorized,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, TenantProfile.__table__, Product.__table__, Order.__table__, OrderItem.__table__,
        DeliveryPerson.__table__, Delivery.__table__,
        OrderBoardSetting.__table__, OrderBoardDevice.__table__, OrderBoardActivation.__table__,
    ])
    session = sessionmaker(bind=engine)()
    session.add_all([
        Tenant(id="tenant-a", slug="tenant-a", name="Loja A", timezone="America/Sao_Paulo"),
        Tenant(id="tenant-b", slug="tenant-b", name="Loja B", is_legacy=True),
    ])
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _context(tenant_id: str) -> TenantContext:
    return TenantContext(tenant_id=tenant_id, source=TenantSource.JOB)


def test_routes_are_registered_and_tv_has_no_mutating_order_route():
    paths = {route.path for route in app.routes}
    assert {
        "/api/order-board/activations",
        "/api/order-board/activations/{activation_id}/status",
        "/api/order-board/snapshot",
        "/api/order-board/heartbeat",
        "/api/admin/order-board/settings",
        "/api/admin/order-board/devices",
        "/api/admin/order-board/activations/approve",
    } <= paths
    public_order_paths = [path for path in paths if path.startswith("/api/order-board/orders")]
    assert public_order_paths == []


def test_global_and_tenant_feature_flags_default_to_off(db, monkeypatch):
    monkeypatch.setattr(
        "backend.services.order_board_service.get_app_settings",
        lambda: SimpleNamespace(ORDER_BOARD_ENABLED=False),
    )
    with pytest.raises(OrderBoardForbidden):
        OrderBoardService(db).create_activation()
    settings = OrderBoardService(db, _context("tenant-a")).get_settings()
    assert settings["enabled"] is False
    assert settings["company_name"] == "Loja A"
    assert settings["logo_url"] is None


def test_tenant_admin_updates_own_board_branding_without_cross_tenant_changes(db):
    service = OrderBoardService(db, _context("tenant-a"))
    updated = service.update_settings(OrderBoardSettingsIn(
        company_name="Empresa Aurora",
        logo_url="/uploads/aurora.png",
        enabled=True,
    ))
    assert updated["company_name"] == "Empresa Aurora"
    assert updated["logo_url"] == "/uploads/aurora.png"
    profile = db.query(TenantProfile).filter_by(tenant_id="tenant-a").one()
    assert profile.trade_name == "Empresa Aurora"
    assert profile.logo_url == "/uploads/aurora.png"

    other = OrderBoardService(db, _context("tenant-b")).get_settings()
    assert other["company_name"] == "Loja B"
    assert other["logo_url"] is None


def test_pairing_uses_one_time_claim_hash_and_is_tenant_isolated(db, monkeypatch):
    monkeypatch.setattr(
        "backend.services.order_board_service.get_app_settings",
        lambda: SimpleNamespace(ORDER_BOARD_ENABLED=True),
    )
    public = OrderBoardService(db)
    activation = public.create_activation()
    claim = activation.pop("_claim_token")
    stored = db.query(OrderBoardActivation).filter_by(id=activation["id"]).one()
    assert stored.code_hash != activation["code"]
    assert stored.claim_token_hash != claim

    tenant_a = OrderBoardService(db, _context("tenant-a"))
    device_payload = tenant_a.approve_activation(activation["code"], "TV Sala", actor_id="admin-a")
    claimed, credential = public.activation_status(activation["id"], claim)
    assert claimed["status"] == "claimed"
    assert credential and claim not in credential
    device = public.authenticate_device(credential)
    assert device.id == device_payload["id"]
    assert device.token_hash not in credential

    # Claiming is one-time: a copied temporary cookie cannot rotate an active
    # device credential after the TV has already received it.
    retried, replacement_credential = public.activation_status(activation["id"], claim)
    assert retried["status"] == "claimed"
    assert replacement_credential is None
    assert public.authenticate_device(credential).id == device.id

    with pytest.raises(OrderBoardUnauthorized):
        public.authenticate_device(f"{device.id}.wrong")
    with pytest.raises(OrderBoardNotFound):
        OrderBoardService(db, _context("tenant-b")).rename_device(device.id, "Intruso")


def test_activation_expires_and_failed_prefix_attempts_are_bounded(db, monkeypatch):
    monkeypatch.setattr(
        "backend.services.order_board_service.get_app_settings",
        lambda: SimpleNamespace(ORDER_BOARD_ENABLED=True),
    )
    public = OrderBoardService(db)
    activation = public.create_activation()
    stored = db.query(OrderBoardActivation).filter_by(id=activation["id"]).one()
    wrong = stored.code_prefix + "ZZZZ"
    service = OrderBoardService(db, _context("tenant-a"))
    for _ in range(5):
        with pytest.raises(OrderBoardNotFound):
            service.approve_activation(wrong, "TV", actor_id="admin-a")
    db.refresh(stored)
    assert stored.status == "cancelled"
    assert stored.failed_attempts == 5


def test_revocation_immediately_invalidates_device_credential(db, monkeypatch):
    monkeypatch.setattr(
        "backend.services.order_board_service.get_app_settings",
        lambda: SimpleNamespace(ORDER_BOARD_ENABLED=True),
    )
    public = OrderBoardService(db)
    activation = public.create_activation()
    claim = activation.pop("_claim_token")
    admin = OrderBoardService(db, _context("tenant-a"))
    device_payload = admin.approve_activation(activation["code"], "TV Sala", actor_id="admin-a")
    _, credential = public.activation_status(activation["id"], claim)
    assert credential is not None
    assert public.authenticate_device(credential).id == device_payload["id"]

    admin.revoke_device(device_payload["id"])
    with pytest.raises(OrderBoardUnauthorized):
        public.authenticate_device(credential)


def test_snapshot_only_exposes_assigned_delivery_orders_and_has_stable_etag(db, monkeypatch):
    monkeypatch.setattr(
        "backend.services.order_board_service.get_app_settings",
        lambda: SimpleNamespace(ORDER_BOARD_ENABLED=True),
    )
    now = datetime.now(timezone.utc)
    db.add_all([
        Product(id="product-a", tenant_id="tenant-a", name="Pizza", description="Pizza",
                price=50, category="Pizzas", product_type="pizza"),
        OrderBoardSetting(
            tenant_id="tenant-a", enabled=True, production_sla_minutes=20,
            dispatch_sla_minutes=5, completed_window_seconds=120,
            polling_interval_seconds=5, sound_enabled=False, max_orders=50,
        ),
        OrderBoardDevice(
            id="device-a", tenant_id="tenant-a", name="TV", token_hash="unused",
            status="active", activated_at=now,
        ),
        DeliveryPerson(
            id="driver-a", tenant_id="tenant-a", name="Carlos Silva", phone="11900000000",
        ),
        TenantProfile(tenant_id="tenant-a", trade_name="Empresa Aurora", logo_url="/brand/logo.png"),
        Order(
            id="order-a", tenant_id="tenant-a", order_code="101", status=OrderStatus.preparing,
            fulfillment_type="delivery", sales_channel="delivery", subtotal=50, total=50,
            created_at=now - timedelta(minutes=30), paid_at=now - timedelta(minutes=30),
            preparation_started_at=now - timedelta(minutes=25), delivery_name="PII NAO PODE SAIR",
            delivery_phone="11999999999", delivery_street="Rua secreta",
        ),
        Order(
            id="order-dine-in", tenant_id="tenant-a", order_code="102", status=OrderStatus.preparing,
            fulfillment_type="dine_in", sales_channel="dine_in", subtotal=10, total=10,
        ),
        Order(
            id="order-unassigned", tenant_id="tenant-a", order_code="103", status=OrderStatus.preparing,
            fulfillment_type="delivery", sales_channel="delivery", subtotal=10, total=10,
        ),
        Order(
            id="order-invalid-driver", tenant_id="tenant-a", order_code="105", status=OrderStatus.preparing,
            fulfillment_type="delivery", sales_channel="delivery", subtotal=10, total=10,
        ),
        Order(
            id="order-on-the-way", tenant_id="tenant-a", order_code="104", status=OrderStatus.on_the_way,
            fulfillment_type="delivery", sales_channel="delivery", subtotal=10, total=10,
        ),
        Order(
            id="order-failed-delivery", tenant_id="tenant-a", order_code="106", status=OrderStatus.preparing,
            fulfillment_type="delivery", sales_channel="delivery", subtotal=10, total=10,
        ),
        Order(
            id="order-cancelled-delivery", tenant_id="tenant-a", order_code="107", status=OrderStatus.ready_for_pickup,
            fulfillment_type="delivery", sales_channel="delivery", subtotal=10, total=10,
        ),
        Order(
            id="order-b", tenant_id="tenant-b", order_code="201", status=OrderStatus.preparing,
            fulfillment_type="delivery", sales_channel="delivery", subtotal=10, total=10,
        ),
    ])
    db.flush()
    db.add_all([
        Delivery(
            id="delivery-a", tenant_id="tenant-a", order_id="order-a",
            delivery_person_id="driver-a", status=DeliveryStatus.assigned,
        ),
        Delivery(
            id="delivery-on-the-way", tenant_id="tenant-a", order_id="order-on-the-way",
            delivery_person_id="driver-a", status=DeliveryStatus.on_the_way,
        ),
        Delivery(
            id="delivery-invalid-driver", tenant_id="tenant-a", order_id="order-invalid-driver",
            delivery_person_id="missing-driver", status=DeliveryStatus.assigned,
        ),
        Delivery(
            id="delivery-failed", tenant_id="tenant-a", order_id="order-failed-delivery",
            delivery_person_id="driver-a", status=DeliveryStatus.failed,
        ),
        Delivery(
            id="delivery-cancelled", tenant_id="tenant-a", order_id="order-cancelled-delivery",
            delivery_person_id="driver-a", status=DeliveryStatus.cancelled,
        ),
    ])
    db.commit()
    device = db.query(OrderBoardDevice).filter_by(id="device-a").one()
    service = OrderBoardService(db)
    first, etag_one = service.snapshot(device)
    second, etag_two = service.snapshot(device)
    assert etag_one == etag_two
    assert [row["id"] for row in first["orders"]] == ["order-a"]
    assert first["tenant"] == {
        "name": "Empresa Aurora",
        "logo_url": "/brand/logo.png",
        "timezone": "America/Sao_Paulo",
    }
    assert "metrics" not in first
    assert first["orders"][0]["delivery"] == {
        "provider_key": "own",
        "provider_label": "Motoboy Próprio",
        "driver_name": "Carlos Silva",
    }
    assert set(first["orders"][0]) == {
        "id", "order_code", "status", "created_at",
        "preparation_started_at", "ready_for_pickup_at", "delivery",
    }
    serialized = repr(first["orders"])
    assert "PII NAO PODE SAIR" not in serialized
    assert "11999999999" not in serialized
    assert "Rua secreta" not in serialized

    profile = db.query(TenantProfile).filter_by(tenant_id="tenant-a").one()
    db.delete(profile)
    db.commit()
    fallback, _ = service.snapshot(device)
    assert fallback["tenant"]["name"] == "Loja A"
    assert fallback["tenant"]["logo_url"] is None


def test_snapshot_orders_lanes_and_age_and_caps_without_cross_tenant_rows(db, monkeypatch):
    monkeypatch.setattr(
        "backend.services.order_board_service.get_app_settings",
        lambda: SimpleNamespace(ORDER_BOARD_ENABLED=True),
    )
    now = datetime.now(timezone.utc)
    db.add_all([
        OrderBoardSetting(tenant_id="tenant-a", enabled=True, max_orders=50),
        OrderBoardDevice(
            id="device-load", tenant_id="tenant-a", name="TV Carga",
            token_hash="unused-load", status="active", activated_at=now,
        ),
        DeliveryPerson(
            id="driver-load-a", tenant_id="tenant-a", name="Ana", phone="11900000001",
        ),
        DeliveryPerson(
            id="driver-load-b", tenant_id="tenant-b", name="Intruso", phone="11900000002",
        ),
    ])
    for index in range(55):
        db.add(Order(
            id=f"load-a-{index:02d}", tenant_id="tenant-a", order_code=f"A{index:03d}",
            status=OrderStatus.ready_for_pickup if index < 3 else OrderStatus.preparing,
            fulfillment_type="delivery", sales_channel="delivery",
            subtotal=10, total=10, created_at=now - timedelta(minutes=55 - index), paid_at=now,
        ))
    db.add(Order(
        id="load-b", tenant_id="tenant-b", order_code="B999", status=OrderStatus.preparing,
        fulfillment_type="delivery", sales_channel="delivery", subtotal=10, total=10,
    ))
    db.flush()
    for index in range(55):
        db.add(Delivery(
            id=f"delivery-load-a-{index:02d}", tenant_id="tenant-a", order_id=f"load-a-{index:02d}",
            delivery_person_id="driver-load-a", status=DeliveryStatus.assigned,
        ))
    db.add(Delivery(
        id="delivery-load-b", tenant_id="tenant-b", order_id="load-b",
        delivery_person_id="driver-load-b", status=DeliveryStatus.assigned,
    ))
    db.commit()

    device = db.query(OrderBoardDevice).filter_by(id="device-load").one()
    payload, _ = OrderBoardService(db).snapshot(device)
    ids = [row["id"] for row in payload["orders"]]
    assert len(ids) == 50
    assert len(ids) == len(set(ids))
    assert "load-b" not in ids
    assert ids[:5] == ["load-a-00", "load-a-01", "load-a-02", "load-a-03", "load-a-04"]
    assert [row["status"] for row in payload["orders"][:4]] == [
        "ready_for_pickup", "ready_for_pickup", "ready_for_pickup", "preparing",
    ]


def test_ready_timestamp_is_only_added_by_official_status_service_and_migration_is_additive():
    service_source = (ROOT / "backend/services/order_service.py").read_text(encoding="utf-8")
    assert 'if new_status == "ready_for_pickup" and not order.ready_for_pickup_at:' in service_source
    assert "order.ready_for_pickup_at = now" in service_source
    migration = (ROOT / "backend/migrations/versions/20260927_order_board_mvp.py").read_text(encoding="utf-8")
    assert 'down_revision = "20260926_dispatch_labels"' in migration
    assert 'sa.Column("ready_for_pickup_at", sa.DateTime(timezone=True), nullable=True)' in migration
    assert "DROP COLUMN" not in migration.split("def upgrade()", 1)[1].split("def downgrade()", 1)[0]
    assert "enabled, production_sla_minutes" in migration and "SELECT id, FALSE" in migration


def test_settings_bounds_are_enforced_by_schema():
    with pytest.raises(ValueError):
        OrderBoardSettingsIn(company_name="Empresa", polling_interval_seconds=1)
    with pytest.raises(ValueError):
        OrderBoardSettingsIn(company_name="Empresa", max_orders=500)
    with pytest.raises(ValueError):
        OrderBoardSettingsIn(company_name="Empresa", logo_url="javascript:alert(1)")
