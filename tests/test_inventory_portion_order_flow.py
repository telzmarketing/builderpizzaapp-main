from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend import main as _all_app_models  # noqa: F401
from backend.models.admin import AdminUser
from backend.models.idempotency import IdempotencyKey
from backend.models.inventory import (
    InventoryCategory,
    InventoryItem,
    InventoryLocation,
    InventoryStockMovement,
    InventoryUnit,
)
from backend.models.inventory_foundation import InventoryLot, InventoryOperation, InventoryReservation
from backend.models.inventory_portion import InventoryPortionConfig
from backend.models.preparation import (
    InventoryOperationRecipe,
    InventoryOperationRecipeItem,
    PreparationExecution,
    PreparationOrder,
)
from backend.models.tenant import Tenant
from backend.schemas.inventory_portion import InventoryPortionConfigIn, InventoryPortionPrepareIn
from backend.services.inventory_portion_service import InventoryPortionConfigService


@pytest.mark.parametrize(
    ("purchase_unit", "initial_stock", "recipe_input"),
    [
        ("kg", Decimal("3"), Decimal("0.15")),
        ("package", Decimal("1"), Decimal("0.03")),
    ],
)
def test_calabresa_portion_order_plans_without_moving_stock(purchase_unit, initial_stock, recipe_input):
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
        IdempotencyKey.__table__,
        InventoryPortionConfig.__table__,
        InventoryOperationRecipe.__table__,
        InventoryOperationRecipeItem.__table__,
        PreparationOrder.__table__,
        PreparationExecution.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        db.add_all([
            AdminUser(id="actor", email="actor@example.invalid", name="Actor", password_hash="x"),
            InventoryUnit(id="kg", tenant_id="tenant-a", name="Quilograma", symbol="KG", code="kg", dimension="mass", conversion_factor=1),
            InventoryUnit(id="gr", tenant_id="tenant-a", name="Grama", symbol="GR", code="gr", dimension="mass", conversion_factor=Decimal("0.001")),
            InventoryUnit(id="package", tenant_id="tenant-a", name="Pacote", symbol="PCT", code="package", dimension="count", conversion_factor=1),
            InventoryLocation(id="loc", tenant_id="tenant-a", name="Estoque"),
            InventoryItem(
                id="calabresa", tenant_id="tenant-a", name="Calabresa", sku="CAL-RAW",
                item_type="ingredient", unit_id=purchase_unit, default_location_id="loc",
                weight_quantity=Decimal("5") if purchase_unit == "package" else None,
                weight_unit_id="kg" if purchase_unit == "package" else None,
            ),
            InventoryStockMovement(
                id="opening-stock", tenant_id="tenant-a", item_id="calabresa", location_id="loc",
                quantity_delta=initial_stock, unit_cost=1, source_type="test", source_id="opening",
                movement_type="in", reason="initial_stock",
            ),
        ])
        db.commit()

        service = InventoryPortionConfigService(db, "tenant-a", "actor")
        config = service.create(
            InventoryPortionConfigIn(
                source_item_id="calabresa", portion_weight=Decimal("150"), unit_id="gr",
                min_stock=Decimal("10"), target_stock=Decimal("100"),
            ),
            f"config-{purchase_unit}",
        )
        output = db.get(InventoryItem, config.output_item_id)
        count_unit = db.get(InventoryUnit, output.unit_id)
        assert output.item_type == "finished_good"
        assert count_unit.code == "portion_count"
        assert count_unit.dimension == "count"
        assert count_unit.symbol == "PRQ"

        before_movements = db.query(InventoryStockMovement).count()
        order = service.create_preparation_order(
            config.id,
            InventoryPortionPrepareIn(target_quantity=Decimal("100")),
            f"prepare-{purchase_unit}",
        )

        saved_order = db.get(PreparationOrder, order["id"])
        recipe = db.get(InventoryOperationRecipe, saved_order.recipe_id)
        recipe_item = db.query(InventoryOperationRecipeItem).filter_by(recipe_id=recipe.id).one()
        assert saved_order.target_quantity == Decimal("100")
        assert saved_order.status == "draft"
        assert order["target_quantity"] == "100"
        assert recipe.output_item_id == output.id
        assert recipe.output_unit_id == count_unit.id
        assert recipe.yield_quantity == Decimal("1")
        assert recipe_item.item_id == "calabresa"
        assert recipe_item.unit_id == purchase_unit
        assert recipe_item.quantity == recipe_input
        assert db.query(InventoryStockMovement).count() == before_movements

        balance = service.balances()[0]
        assert balance["source_stock"] == initial_stock
        assert balance["source_unit_symbol"] == ("KG" if purchase_unit == "kg" else "PCT")
        assert balance["physical_stock"] == Decimal("0")
        assert balance["available_stock"] == Decimal("0")

        service.deactivate(config.id, f"deactivate-{purchase_unit}")
        replacement = service.create(
            InventoryPortionConfigIn(
                source_item_id="calabresa", portion_weight=Decimal("150"), unit_id="gr",
                min_stock=Decimal("10"), target_stock=Decimal("100"),
            ),
            f"replacement-{purchase_unit}",
        )
        assert replacement.id != config.id
        assert replacement.output_item_id != config.output_item_id
        assert db.get(PreparationOrder, saved_order.id).recipe_id == recipe.id
    finally:
        db.close()
        engine.dispose()
