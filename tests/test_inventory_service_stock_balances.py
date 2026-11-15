from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend import main as _all_app_models  # noqa: F401
from backend.models.inventory_foundation import InventoryReservation
from backend.services.inventory_service import InventoryService


def _item(item_id="item-a", tenant_id="tenant-a"):
    return SimpleNamespace(
        id=item_id,
        tenant_id=tenant_id,
        name="Brócolis",
        sku="INS-BROCOLIS",
        item_type="ingredient",
        portionable=False,
        category_id=None,
        category=None,
        unit_id=None,
        unit=None,
        weight_quantity=None,
        weight_unit_id=None,
        weight_unit=None,
        default_location_id=None,
        default_location=None,
        min_stock=Decimal("0"),
        notes=None,
        active=True,
        created_at=None,
        updated_at=None,
    )


def test_serialize_item_reports_tenant_scoped_unexpired_reservations():
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[InventoryReservation.__table__])
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        now = datetime.now(timezone.utc)
        db.add_all([
            InventoryReservation(
                id="active", tenant_id="tenant-a", business_key="active", item_id="item-a", location_id="loc",
                quantity=Decimal("6"), source_type="order", source_id="order-a", status="active",
                expires_at=now + timedelta(hours=1), actor_id="actor",
            ),
            InventoryReservation(
                id="never", tenant_id="tenant-a", business_key="never", item_id="item-a", location_id="loc",
                quantity=Decimal("1"), source_type="order", source_id="order-b", status="active",
                expires_at=None, actor_id="actor",
            ),
            InventoryReservation(
                id="expired", tenant_id="tenant-a", business_key="expired", item_id="item-a", location_id="loc",
                quantity=Decimal("20"), source_type="order", source_id="order-c", status="active",
                expires_at=now - timedelta(seconds=1), actor_id="actor",
            ),
            InventoryReservation(
                id="other-tenant", tenant_id="tenant-b", business_key="other-tenant", item_id="item-a", location_id="loc",
                quantity=Decimal("30"), source_type="order", source_id="order-d", status="active",
                expires_at=now + timedelta(hours=1), actor_id="actor",
            ),
        ])
        db.commit()

        result = InventoryService(db, "tenant-a")._serialize_item(
            _item(),
            balances={"item-a": Decimal("10")},
        )

        assert result["current_stock"] == Decimal("10.000000")
        assert result["reserved_stock"] == Decimal("7.000000")
        assert result["available_stock"] == Decimal("3.000000")
    finally:
        db.close()
        engine.dispose()


def test_serialize_item_clamps_available_stock_at_zero():
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[InventoryReservation.__table__])
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        now = datetime.now(timezone.utc)
        db.add(InventoryReservation(
            id="active", tenant_id="tenant-a", business_key="active", item_id="item-a", location_id="loc",
            quantity=Decimal("12"), source_type="preparation", source_id="prep-a", status="active",
            expires_at=now + timedelta(hours=1), actor_id="actor",
        ))
        db.commit()

        result = InventoryService(db, "tenant-a")._serialize_item(
            _item(),
            balances={"item-a": Decimal("10")},
        )

        assert result["reserved_stock"] == Decimal("12.000000")
        assert result["available_stock"] == Decimal("0.000000")
    finally:
        db.close()
        engine.dispose()
