"""Portion arithmetic and real PostgreSQL stock/recipe transaction regressions."""
import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest
from backend.services.recipe_resolution import resolve_recipes, required_ingredients


def recipe(product, role="flavor", reference=.5, **scope):
    values = dict(id=str(uuid.uuid4()), product_id=product, component_role=role,
                  reference_fraction=reference, product_size_id=None, product_crust_type_id=None,
                  product_drink_variant_id=None, complement_key=None,
                  items=[NS(inventory_item_id=role + product, quantity=100, waste_percent=0)])
    values.update(scope)
    return NS(**values)


def cart(slots, primary="A", **options):
    values = dict(product_id=primary, quantity=1, selected_size_id=None, selected_size=None,
                  selected_crust_type_id=None, selected_border_id=None, selected_drink_variant_id=None,
                  add_ons=[], flavors=[NS(product_id=value) for value in slots])
    values.update(options)
    return NS(**values)


@pytest.mark.parametrize("slots,multipliers", [("A", [2]), ("AB", [1, 1]), ("ABC", [2/3]*3), ("AAB", [4/3, 2/3])])
def test_half_reference_occupied_portion_and_repeated_flavor(slots, multipliers):
    result = resolve_recipes(cart(slots), {pid: [recipe(pid)] for pid in set(slots)})
    assert not result.missing
    assert [row.multiplier for row in result.uses] == pytest.approx(multipliers)
    assert sum(required_ingredients(result).values()) == pytest.approx(200)


def test_legacy_whole_reference_and_whole_base_packaging():
    recipes = {"A": [recipe("A", reference=1), recipe("A", "base", 1), recipe("A", "packaging", 1)], "B": [recipe("B", reference=1)]}
    result = resolve_recipes(cart("AB"), recipes)
    assert [(use.recipe.component_role, use.multiplier) for use in result.uses] == [("flavor", .5), ("base", 1), ("packaging", 1), ("flavor", .5)]


def test_base_is_used_when_primary_product_is_not_a_selected_flavor():
    result = resolve_recipes(cart("BC"), {"A": [recipe("A", "base", 1)], "B": [recipe("B")], "C": [recipe("C")]})
    assert not result.missing
    assert sum(use.multiplier for use in result.uses if use.recipe.component_role == "base") == 1


def test_partial_recipe_missing_and_selected_border_mass_are_distinct():
    assert resolve_recipes(cart("AB"), {"A": [recipe("A")]}).missing == ("product:B",)
    recipes = {"A": [recipe("A"), recipe("A", "crust", 1, product_crust_type_id="dough"), recipe("A", "crust", 1, product_crust_type_id="border")]}
    result = resolve_recipes(cart("A", selected_crust_type_id="dough", selected_border_id="border"), recipes)
    assert not result.missing
    assert len(result.uses) == 3


def test_selected_options_need_a_recipe_matching_the_whole_configuration():
    recipes = {"A": [recipe("A"), recipe("A", "crust", 1, product_size_id="large", product_crust_type_id="border")]}
    result = resolve_recipes(cart("A", selected_size_id="small", selected_border_id="border"), recipes)
    assert "crust:border" in result.missing
    addon = recipe("A", "addon", 1, complement_key="extra-cheese")
    assert len(resolve_recipes(cart("A", add_ons=["Extra Cheese"]), {"A": [recipe("A"), addon]}).uses) == 2


@pytest.fixture
def pg_inventory():
    url = os.environ.get("PRODUCT_AUDIT_DATABASE_URL")
    if not url:
        pytest.skip("Requires an explicitly configured disposable PostgreSQL database")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.main import app  # register model relationships, no startup
    from backend.core.tenant_context import TenantContext, TenantSource
    from backend.core.wave6_tenant_context import bind_wave6_tenant_context
    from backend.models.tenant import Tenant
    from backend.models.product import Product
    from backend.models.inventory import InventoryItem, InventoryStockMovement, InventoryRecipeVersion, InventoryRecipeItem
    from backend.models.gestao import GestaoModuleSettings
    from backend.services.inventory_service import InventoryService

    engine = create_engine(url, connect_args={"connect_timeout": 5})
    assert engine.dialect.name == "postgresql"
    with engine.connect() as connection:
        transaction = connection.begin()
        db = Session(bind=connection, join_transaction_mode="create_savepoint", autoflush=False)
        try:
            tid = "recipe-" + uuid.uuid4().hex
            context = TenantContext(tid, TenantSource.JOB)
            bind_wave6_tenant_context(db, context)
            db.add(Tenant(id=tid, slug=tid, name="Synthetic recipe tenant"))
            db.flush()
            product = Product(id=uuid.uuid4().hex, tenant_id=tid, name="Synthetic pizza", description="test", price=50, product_type="pizza")
            stock = InventoryItem(id=uuid.uuid4().hex, tenant_id=tid, name="Synthetic cheese")
            db.add_all([product, stock])
            db.add(GestaoModuleSettings(id=uuid.uuid4().hex, tenant_id=tid, module_key="inventory", title="Inventory", enabled=True, status="active", settings_json='{"sales_control_enabled":true,"auto_consume_on_preparing":true}'))
            db.flush()
            version = InventoryRecipeVersion(id=uuid.uuid4().hex, tenant_id=tid, product_id=product.id, component_role="flavor", reference_fraction=.5, version_number=1, active=True)
            db.add(version)
            db.add(InventoryStockMovement(id=uuid.uuid4().hex, tenant_id=tid, item_id=stock.id, source_type="manual_entry", movement_type="in", quantity_delta=500, unit_cost=1))
            db.flush()
            db.add(InventoryRecipeItem(id=uuid.uuid4().hex, tenant_id=tid, recipe_id=version.id, inventory_item_id=stock.id, quantity=100, waste_percent=0))
            db.flush()
            yield NS(db=db, tid=tid, context=context, product=product, stock=stock, recipe=version, service=InventoryService(db, tid, context))
        finally:
            db.close()
            transaction.rollback()
    engine.dispose()


def test_pg_aggregate_stock_prevents_separate_lines_exceeding_balance(pg_inventory):
    from backend.services.inventory_service import ProductInventoryAvailabilityService, InventoryUnavailable
    p = pg_inventory
    line = cart([p.product.id], primary=p.product.id)
    availability = ProductInventoryAvailabilityService(p.db, p.tid, p.context)
    availability.validate_cart_items([line, line])  # 400 <= 500
    with pytest.raises(InventoryUnavailable):
        availability.validate_cart_items([line, line, line])  # 600 > 500


def test_pg_stock_only_preparing_idempotence_and_cancellation_loss(pg_inventory):
    from backend.models.order import Order, OrderItem, OrderStatus
    from backend.models.inventory import InventoryStockMovement
    from backend.services.cmv_snapshot_service import OrderCmvSnapshotService
    p = pg_inventory
    order = Order(id=uuid.uuid4().hex, tenant_id=p.tid, status=OrderStatus.paid, subtotal=50, total=50, fulfillment_type="pickup")
    p.db.add(order)
    p.db.flush()
    p.db.add(OrderItem(id=uuid.uuid4().hex, tenant_id=p.tid, order_id=order.id, product_id=p.product.id, quantity=1, unit_price=50, total_price=50))
    p.db.flush()
    assert p.service.consume_order_sale(order.id)["reason"] == "not_preparing"
    assert p.service._stock_balance_map()[p.stock.id] == 500
    # Stock quantities freeze even with CMV dashboard disabled.
    snapshot = OrderCmvSnapshotService(p.db, p.tid, p.context).create_for_order(order)
    p.db.flush()
    assert snapshot and not snapshot.missing_recipe
    from backend.schemas.inventory import InventoryRecipeVersionIn
    p.service.update_product_recipe(p.product.id, p.recipe.id, InventoryRecipeVersionIn(reference_fraction=.5, items=[dict(inventory_item_id=p.stock.id, quantity=150)]))
    # The sale's frozen quantity remains 200, although a new recipe is now 300.
    order.status = OrderStatus.preparing
    order.preparation_started_at = datetime.now(timezone.utc)
    p.db.flush()
    assert p.service.consume_order_sale(order.id)["deducted"]
    assert p.service.consume_order_sale(order.id)["reason"] == "already_deducted"
    assert p.service._stock_balance_map()[p.stock.id] == 300
    assert p.service.reverse_order_sale(order.id)["reason"] == "production_loss_recorded"
    assert p.service.reverse_order_sale(order.id)["reason"] == "loss_already_recorded"
    assert p.service._stock_balance_map()[p.stock.id] == 300
    loss = p.db.query(InventoryStockMovement).filter_by(tenant_id=p.tid, source_type="order_sale_loss", source_id=order.id).one()
    assert loss.quantity_delta == 0 and '"consumed_quantity": 200.0' in loss.notes


def test_pg_recipe_updates_publish_new_version_and_preserve_old_items(pg_inventory):
    from backend.schemas.inventory import InventoryRecipeVersionIn
    from backend.models.inventory import InventoryRecipeItem
    p = pg_inventory
    old_id = p.recipe.id
    result = p.service.update_product_recipe(p.product.id, old_id, InventoryRecipeVersionIn(component_role="flavor", reference_fraction=.5, items=[dict(inventory_item_id=p.stock.id, quantity=150)]))
    assert result["id"] != old_id and result["version_number"] == 2
    assert p.db.query(InventoryRecipeItem).filter_by(recipe_id=old_id).one().quantity == 100
    assert not p.recipe.active


def test_pg_snapshot_marks_missing_secondary_recipe_and_blocks_partial_consumption(pg_inventory):
    from backend.models.product import Product
    from backend.models.order import Order, OrderItem, OrderStatus
    from backend.services.cmv_snapshot_service import OrderCmvSnapshotService, CmvOrderItemContext
    from backend.services.inventory_service import InventoryInvalidReference
    p = pg_inventory
    second = Product(id=uuid.uuid4().hex, tenant_id=p.tid, name="No recipe", description="test", price=50, product_type="pizza")
    order = Order(id=uuid.uuid4().hex, tenant_id=p.tid, status=OrderStatus.preparing, subtotal=50, total=50, fulfillment_type="pickup", preparation_started_at=datetime.now(timezone.utc))
    p.db.add_all([second, order])
    p.db.flush()
    item = OrderItem(id=uuid.uuid4().hex, tenant_id=p.tid, order_id=order.id, product_id=p.product.id, quantity=1, unit_price=50, total_price=50)
    p.db.add(item)
    p.db.flush()
    selection = cart([p.product.id, second.id], primary=p.product.id)
    snapshot = OrderCmvSnapshotService(p.db, p.tid, p.context).create_for_order(order, [CmvOrderItemContext(item, selection)])
    p.db.flush()
    assert snapshot.missing_recipe and snapshot.items[0].missing_recipe
    with pytest.raises(InventoryInvalidReference):
        p.service.consume_order_sale(order.id)
    assert p.service._stock_balance_map()[p.stock.id] == 500


@pytest.mark.parametrize("same_order", [True, False])
def test_pg_concurrent_preparation_serializes_idempotence_and_shared_stock(same_order):
    """Independent committed sessions exercise actual PostgreSQL row locks."""
    url = os.environ.get("PRODUCT_AUDIT_DATABASE_URL")
    if not url:
        pytest.skip("Requires an explicitly configured disposable PostgreSQL database")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    from backend.main import app  # noqa: F401
    from backend.core.tenant_context import TenantContext, TenantSource
    from backend.models.order import Order, OrderItem, OrderStatus
    from backend.models.inventory import InventoryItem, InventoryRecipeVersion, InventoryRecipeItem, InventoryStockMovement
    from backend.models.gestao import GestaoModuleSettings
    from backend.services.inventory_service import InventoryService, InventoryUnavailable, InventoryInvalidReference

    engine = create_engine(url, connect_args={"connect_timeout": 5})
    schema = "recipe_lock_" + uuid.uuid4().hex
    tables = ("orders", "order_items", "order_item_flavors", "inventory_items", "inventory_recipe_versions", "inventory_recipe_items", "inventory_stock_movements", "gestao_module_settings", "order_cmv_snapshots", "inventory_lots", "inventory_operations", "inventory_reservations")
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            for table in tables:
                conn.execute(text(f'CREATE TABLE "{schema}"."{table}" (LIKE public."{table}" INCLUDING ALL)'))
        isolated = engine.execution_options(schema_translate_map={None: schema})
        tenant = "synthetic"
        context = TenantContext(tenant, TenantSource.JOB)
        with Session(isolated) as db:
            db.add(InventoryItem(id="stock", tenant_id=tenant, name="Stock"))
            db.add(GestaoModuleSettings(id="settings", tenant_id=tenant, module_key="inventory", title="Inventory", enabled=True, status="active", settings_json='{"sales_control_enabled":true,"auto_consume_on_preparing":true}'))
            db.add(GestaoModuleSettings(id="settings-other", tenant_id="other", module_key="inventory", title="Inventory", enabled=True, status="active", settings_json='{"sales_control_enabled":true,"auto_consume_on_preparing":true}'))
            db.add(InventoryStockMovement(id="entry", tenant_id=tenant, item_id="stock", source_type="manual_entry", movement_type="in", quantity_delta=300, unit_cost=1))
            db.add(InventoryRecipeVersion(id="recipe", tenant_id=tenant, product_id="pizza", component_role="flavor", reference_fraction=.5, active=True))
            db.add(InventoryRecipeItem(id="ingredient", tenant_id=tenant, recipe_id="recipe", inventory_item_id="stock", quantity=100, waste_percent=0))
            for index in range(1 if same_order else 2):
                oid = f"order{index}"
                db.add(Order(id=oid, tenant_id=tenant, status=OrderStatus.preparing, subtotal=50, total=50, fulfillment_type="pickup", preparation_started_at=datetime.now(timezone.utc)))
                db.add(OrderItem(id=f"item{index}", tenant_id=tenant, order_id=oid, product_id="pizza", quantity=1, unit_price=50, total_price=50))
            db.commit()
        barrier = Barrier(2)

        def start(index):
            with Session(isolated, autoflush=False) as db:
                barrier.wait(timeout=10)
                try:
                    result = InventoryService(db, tenant, context).consume_order_sale(f"order{0 if same_order else index}")
                    db.commit()
                    return result["reason"]
                except InventoryUnavailable:
                    db.rollback()
                    return "insufficient"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(start, [0, 1]))
        assert sorted(outcomes) == sorted(["ok", "already_deducted" if same_order else "insufficient"])
        with Session(isolated) as db:
            assert InventoryService(db, tenant, context)._stock_balance_map()["stock"] == 100
            wrong_context = TenantContext("other", TenantSource.JOB)
            with pytest.raises(InventoryInvalidReference):
                InventoryService(db, "other", wrong_context).consume_order_sale("order0")
    finally:
        # Only this test-created, UUID-named synthetic schema is removed.
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
