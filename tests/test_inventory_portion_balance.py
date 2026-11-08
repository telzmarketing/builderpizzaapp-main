from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend import main as _all_app_models  # noqa: F401
from backend.models.admin import AdminUser
from backend.models.tenant import Tenant
from backend.models.inventory import InventoryCategory, InventoryItem, InventoryLocation, InventoryStockMovement, InventoryUnit
from backend.models.inventory_foundation import InventoryLot, InventoryOperation, InventoryReservation
from backend.models.preparation import InventoryOperationRecipe, PreparationOrder
from backend.services.inventory_portion_service import InventoryPortionConfigService


def test_portion_balance_uses_ledger_valid_reservations_and_open_preparation_without_cross_tenant_rows(monkeypatch):
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    tables = [
        Tenant.__table__,
        AdminUser.__table__,
        InventoryCategory.__table__,
        InventoryLocation.__table__,
        InventoryUnit.__table__,
        InventoryItem.__table__,
        InventoryOperation.__table__,
        InventoryLot.__table__,
        InventoryStockMovement.__table__,
        InventoryReservation.__table__,
        InventoryOperationRecipe.__table__,
        PreparationOrder.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        now = datetime.now(timezone.utc)
        db.add_all([
            AdminUser(id="actor", email="actor@example.invalid", name="Actor", password_hash="x"),
            InventoryUnit(id="g", tenant_id="tenant-a", name="Grama", symbol="g", code="g", dimension="mass", conversion_factor=1),
            InventoryLocation(id="loc", tenant_id="tenant-a", name="Câmara"),
            InventoryItem(id="portion-a", tenant_id="tenant-a", name="Mussarela 150 g", sku="POR-A", unit_id="g", default_location_id="loc", item_type="finished_good"),
            InventoryOperationRecipe(id="recipe-a", tenant_id="tenant-a", name="Mussarela preparada", output_item_id="portion-a", output_unit_id="g", yield_quantity=10, created_by="actor"),
            InventoryOperation(id="op-a", tenant_id="tenant-a", kind="manual_in", business_key="in-a", idempotency_scope="test", idempotency_key="in-a", request_hash="a" * 64, actor_id="actor", status="committed"),
            InventoryStockMovement(id="movement-a", tenant_id="tenant-a", item_id="portion-a", location_id="loc", quantity_delta=10, unit_cost=2, operation_id="op-a", operation_sequence=1, source_type="test", source_id="a", movement_type="in", reason="test"),
            InventoryReservation(id="reservation-valid", tenant_id="tenant-a", business_key="reservation-valid", item_id="portion-a", location_id="loc", quantity=2, source_type="order", source_id="order-a", status="active", expires_at=now + timedelta(hours=1), actor_id="actor"),
            InventoryReservation(id="reservation-expired", tenant_id="tenant-a", business_key="reservation-expired", item_id="portion-a", location_id="loc", quantity=4, source_type="order", source_id="order-old", status="active", expires_at=now - timedelta(hours=1), actor_id="actor"),
            PreparationOrder(id="prep-a", tenant_id="tenant-a", recipe_id="recipe-a", target_quantity=5, produced_quantity=1, lost_quantity=1, discarded_quantity=0, status="in_progress", version=1, idempotency_key="prep-a", actor_id="actor"),
        ])
        db.commit()

        config = SimpleNamespace(
            id="config-a", output_item_id="portion-a", output_item=SimpleNamespace(name="Mussarela 150 g"),
            source_item=SimpleNamespace(name="Mussarela"), unit=SimpleNamespace(symbol="g"),
            portion_weight=Decimal("1"), yield_percent=Decimal("100"), min_stock=Decimal("3"), target_stock=Decimal("10"), active=True,
        )
        service = InventoryPortionConfigService(db, "tenant-a", "actor")
        monkeypatch.setattr(service, "list", lambda active=None: [config])

        result = service.balances()

        assert result == [{
            "config_id": "config-a", "output_item_id": "portion-a", "output_item_name": "Mussarela - porcao 1 g",
            "source_item_name": "Mussarela", "unit_symbol": "g", "usage": "mandatory", "physical_stock": Decimal("10.000000"),
            "reserved_stock": Decimal("2.000000"), "available_stock": Decimal("8.000000"),
            "in_preparation": Decimal("3.000000"), "min_stock": Decimal("3"),
            "target_stock": Decimal("10"), "active": True, "unit_cost": Decimal("2.00000000"), "next_expiry": None,
        }]

        alerts = service.replenishment_alerts()
        assert alerts[0]["status"] == "ok"
        assert alerts[0]["suggested_portions"] == Decimal("0")
    finally:
        db.close()
        engine.dispose()
