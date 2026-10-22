"""Real PostgreSQL guards for additive recipe details and conversion evidence."""
import os
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def recipe_details_db():
    url = os.environ.get("INVENTORY_FOUNDATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires an explicitly configured disposable PostgreSQL database")
    from backend.main import app  # noqa: F401 -- register real metadata without startup
    from backend.models.tenant import Tenant
    from backend.models.product import Product
    from backend.models.inventory import InventoryUnit, InventoryItem, InventoryRecipeVersion

    engine = sa.create_engine(url, connect_args={"connect_timeout": 5})
    assert engine.dialect.name == "postgresql"
    ids = {name: name + "-" + uuid.uuid4().hex for name in (
        "tenant", "other_tenant", "kg", "g", "foreign_unit", "product", "item", "recipe",
    )}
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            for key in ("tenant", "other_tenant"):
                connection.execute(Tenant.__table__.insert().values(id=ids[key], slug=ids[key], name="Recipe constraints"))
            for key, tenant_key in (("kg", "tenant"), ("g", "tenant"), ("foreign_unit", "other_tenant")):
                connection.execute(InventoryUnit.__table__.insert().values(id=ids[key], tenant_id=ids[tenant_key], name=key, symbol=key))
            connection.execute(Product.__table__.insert().values(id=ids["product"], tenant_id=ids["tenant"], name="Pizza", description="test", price=10))
            connection.execute(InventoryItem.__table__.insert().values(id=ids["item"], tenant_id=ids["tenant"], name="Internal stock name", unit_id=ids["kg"]))
            connection.execute(InventoryRecipeVersion.__table__.insert().values(
                id=ids["recipe"], tenant_id=ids["tenant"], product_id=ids["product"], reference_fraction=Decimal("0.5"),
            ))
            yield connection, ids
        finally:
            transaction.rollback()
    engine.dispose()


def line(ids, **changes):
    values = dict(id=uuid.uuid4().hex, tenant_id=ids["tenant"], recipe_id=ids["recipe"],
                  inventory_item_id=ids["item"], quantity=Decimal("1.234567"))
    values.update(changes)
    return values


def rejected(connection, table, values):
    with connection.begin_nested() as savepoint:
        with pytest.raises(IntegrityError):
            connection.execute(table.insert().values(**values))
        savepoint.rollback()


def test_legacy_recipe_details_remain_unknown_and_internal_names_stay_private(recipe_details_db):
    from backend.models.inventory import InventoryRecipeItem, InventoryRecipeVersion
    connection, ids = recipe_details_db
    values = line(ids)
    connection.execute(InventoryRecipeItem.__table__.insert().values(**values))
    stored = connection.execute(sa.select(InventoryRecipeItem.__table__).where(InventoryRecipeItem.id == values["id"])).mappings().one()
    assert stored["quantity"] == Decimal("1.234567")
    assert stored["unit_id"] is None
    assert stored["entered_unit_id"] is None
    assert stored["entered_quantity"] is None
    assert stored["conversion_factor_snapshot"] is None
    assert stored["public_name"] is None
    assert stored["show_public"] is False
    assert stored["allow_removal"] is False
    assert stored["position"] == 0
    recipe = connection.execute(sa.select(InventoryRecipeVersion.__table__).where(InventoryRecipeVersion.id == ids["recipe"])).mappings().one()
    assert recipe["instructions"] is None
    assert recipe["preparation_steps"] == []
    assert recipe["reference_image_url"] is None


@pytest.mark.parametrize("field", ["unit_id", "entered_unit_id"])
def test_recipe_units_are_tenant_scoped(recipe_details_db, field):
    from backend.models.inventory import InventoryRecipeItem
    connection, ids = recipe_details_db
    values = line(ids, unit_id=ids["kg"], entered_unit_id=ids["g"],
                  entered_quantity=Decimal("1234.567"), conversion_factor_snapshot=Decimal("0.001"))
    values[field] = ids["foreign_unit"]
    rejected(connection, InventoryRecipeItem.__table__, values)


@pytest.mark.parametrize("changes", [
    {"entered_unit_id": None}, {"entered_quantity": None}, {"conversion_factor_snapshot": None},
    {"unit_id": None}, {"quantity": Decimal("2")}, {"conversion_factor_snapshot": Decimal("NaN")},
])
def test_conversion_evidence_is_complete_finite_and_matches_base_quantity(recipe_details_db, changes):
    from backend.models.inventory import InventoryRecipeItem
    connection, ids = recipe_details_db
    values = line(ids, unit_id=ids["kg"], entered_unit_id=ids["g"],
                  entered_quantity=Decimal("1234.567"), conversion_factor_snapshot=Decimal("0.001"))
    rejected(connection, InventoryRecipeItem.__table__, {**values, **changes})


def test_conversion_evidence_preserves_input_without_replacing_normalized_quantity(recipe_details_db):
    from backend.models.inventory import InventoryRecipeItem
    connection, ids = recipe_details_db
    values = line(ids, unit_id=ids["kg"], entered_unit_id=ids["g"],
                  entered_quantity=Decimal("1234.567"), conversion_factor_snapshot=Decimal("0.001"))
    connection.execute(InventoryRecipeItem.__table__.insert().values(**values))
    stored = connection.execute(sa.select(InventoryRecipeItem.__table__).where(InventoryRecipeItem.id == values["id"])).mappings().one()
    assert stored["quantity"] == Decimal("1.234567")
    assert stored["entered_quantity"] == Decimal("1234.567")
    assert stored["conversion_factor_snapshot"] == Decimal("0.001")


@pytest.mark.parametrize("public_name", [None, "", "   "])
def test_public_visibility_requires_an_explicit_nonempty_public_name(recipe_details_db, public_name):
    from backend.models.inventory import InventoryRecipeItem
    connection, ids = recipe_details_db
    rejected(connection, InventoryRecipeItem.__table__, line(ids, show_public=True, public_name=public_name))


def test_negative_position_and_nonarray_steps_are_rejected(recipe_details_db):
    from backend.models.inventory import InventoryRecipeItem, InventoryRecipeVersion
    connection, ids = recipe_details_db
    rejected(connection, InventoryRecipeItem.__table__, line(ids, position=-1))
    rejected(connection, InventoryRecipeVersion.__table__, dict(
        id=uuid.uuid4().hex, tenant_id=ids["tenant"], product_id=ids["product"], preparation_steps={"wrong": "shape"},
    ))


def test_snapshot_customizations_and_recipe_operation_kinds_exist_in_applied_schema(recipe_details_db):
    connection, _ = recipe_details_db
    inspector = sa.inspect(connection)
    for table, column in (
        ("order_item_cmv_snapshots", "composition_json"), ("order_items", "customizations"),
        ("table_session_items", "customizations"),
    ):
        columns = {value["name"]: value for value in inspector.get_columns(table)}
        assert column in columns
        assert isinstance(columns[column]["type"], sa.JSON)
    checks = {value["name"]: value["sqltext"] for value in inspector.get_check_constraints("inventory_operations")}
    assert "recipe_publication" in checks["ck_inventory_operation_kind"]
    assert "recipe_archive" in checks["ck_inventory_operation_kind"]
