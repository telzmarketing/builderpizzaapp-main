import inspect

from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sqlalchemy as sa

from backend.database import Base
from backend import main as _all_app_models  # noqa: F401
from backend.models.preparation import InventoryOperationRecipe
from backend.routes import preparation as preparation_routes
from backend.services.preparation_service import PreparationService


def _session_with_recipes():
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[InventoryOperationRecipe.__table__])
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    db.add_all(
        [
            InventoryOperationRecipe(
                id="recipe-a-active",
                tenant_id="tenant-a",
                name="Massa base",
                output_item_id="output-a",
                output_unit_id="unit-a",
                yield_quantity=10,
                version_number=1,
                created_by="admin-a",
                active=True,
            ),
            InventoryOperationRecipe(
                id="recipe-a-inactive",
                tenant_id="tenant-a",
                name="Recheio arquivado",
                output_item_id="output-a",
                output_unit_id="unit-a",
                yield_quantity=5,
                version_number=1,
                created_by="admin-a",
                active=False,
            ),
            InventoryOperationRecipe(
                id="recipe-b-active",
                tenant_id="tenant-b",
                name="Receita de outro tenant",
                output_item_id="output-b",
                output_unit_id="unit-b",
                yield_quantity=7,
                version_number=1,
                created_by="admin-b",
                active=True,
            ),
        ]
    )
    db.commit()
    return engine, db


def test_list_recipes_is_tenant_scoped_and_defaults_to_active():
    engine, db = _session_with_recipes()
    try:
        result = PreparationService(db, "tenant-a", "admin-a").list_recipes()

        assert [recipe["id"] for recipe in result] == ["recipe-a-active"]
        assert result[0]["yield_quantity"] == "10.000000"
        assert result[0]["active"] is True
    finally:
        db.close()
        engine.dispose()


def test_list_recipes_can_include_inactive_rows_without_cross_tenant_data():
    engine, db = _session_with_recipes()
    try:
        result = PreparationService(db, "tenant-a", "admin-a").list_recipes(active=None)

        assert [recipe["id"] for recipe in result] == [
            "recipe-a-active",
            "recipe-a-inactive",
        ]
        assert all(recipe["id"] != "recipe-b-active" for recipe in result)
    finally:
        db.close()
        engine.dispose()


def test_recipe_listing_route_is_read_only_and_uses_inventory_view_rbac():
    route = next(
        route
        for route in preparation_routes.router.routes
        if getattr(route, "path", None) == "/preparation/recipes"
        and "GET" in route.methods
    )

    assert route.response_model == list[preparation_routes.RecipeOut]
    assert "list_recipes" in inspect.getsource(route.endpoint)
    assert any(
        dependency.call is preparation_routes.view
        for dependency in route.dependant.dependencies
    )
