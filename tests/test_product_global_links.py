"""Focused contracts for additive global-to-product catalog associations."""
from __future__ import annotations

import importlib.util
import importlib
from io import StringIO
from pathlib import Path

import pytest
import backend.models
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from backend.models.product import ProductCrustType, ProductSize
from backend.models.catalog_global import PizzaGlobalCrust
from backend.schemas.catalog_global import GlobalCatalogCreate, ProductOptionAssociationCreate, ProductSizeAssociationCreate
from backend.routes.catalog_global import _create, _delete
from backend.core.tenant_context import TenantContext, TenantSource
from backend.schemas.product import ProductCrustTypeOut, ProductSizeOut


ROOT = Path(__file__).parents[1]


for _module in (ROOT / "backend" / "models").glob("*.py"):
    if _module.name != "__init__.py":
        importlib.import_module(f"backend.models.{_module.stem}")


def _migration():
    path = ROOT / "backend/migrations/versions/20261106_product_global_links.py"
    spec = importlib.util.spec_from_file_location("product_global_links", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_option_models_have_nullable_global_links_and_border_override():
    assert {"global_size_id"}.issubset(ProductSize.__table__.columns.keys())
    assert {"global_dough_type_id", "global_crust_id", "price_addition_override"}.issubset(ProductCrustType.__table__.columns.keys())
    assert ProductSize.__table__.columns["global_size_id"].nullable is True
    assert ProductCrustType.__table__.columns["price_addition_override"].nullable is True


def test_association_inputs_require_valid_global_ids_and_prices():
    with pytest.raises(ValidationError):
        ProductSizeAssociationCreate(global_size_id="", price=20)
    with pytest.raises(ValidationError):
        ProductSizeAssociationCreate(global_size_id="size-1", price=0)
    with pytest.raises(ValidationError):
        ProductOptionAssociationCreate(price_addition_override=-0.01)


def test_existing_outputs_remain_compatible_and_expose_optional_links():
    assert ProductSizeOut.model_fields["global_size_id"].is_required() is False
    assert ProductCrustTypeOut.model_fields["global_crust_id"].is_required() is False
    assert ProductCrustTypeOut.model_fields["price_addition_override"].is_required() is False


def test_migration_is_expand_only_and_chained_to_global_catalog():
    migration = _migration()
    assert migration.down_revision == "20261106_global_catalog"
    output = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
    operations = Operations(context)
    with Operations.context(operations.migration_context):
        migration.upgrade()
    sql = output.getvalue()
    assert "global_size_id" in sql
    assert "global_dough_type_id" in sql
    assert "global_crust_id" in sql
    assert "price_addition_override" in sql
    assert "DROP TABLE" not in sql
    assert "DROP TABLE" not in sql.upper()


def test_global_crust_create_delete_is_physical_and_recreate_is_new_record():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    PizzaGlobalCrust.__table__.create(engine)
    ProductCrustType.__table__.create(engine)
    context = TenantContext(tenant_id="tenant-a", source=TenantSource.JOB)
    with Session(engine) as db:
        created = _create(
            db, PizzaGlobalCrust,
            GlobalCatalogCreate(name="Catupiry", price_addition=14),
            context, "global-crust",
        )
        assert created.id.startswith("global-crust-")
        assert created.tenant_id == "tenant-a"
        _delete(db, PizzaGlobalCrust, created.id, context, physical=True)
        assert db.get(PizzaGlobalCrust, created.id) is None

        recreated = _create(
            db, PizzaGlobalCrust,
            GlobalCatalogCreate(name="Catupiry", description="Nova", price_addition=16),
            context, "global-crust",
        )
        assert recreated.id != created.id
        assert recreated.active is True
        assert recreated.description == "Nova"
        assert recreated.price_addition == 16
        assert db.query(PizzaGlobalCrust).filter(PizzaGlobalCrust.tenant_id == "tenant-a").count() == 1
    engine.dispose()


def test_global_crust_delete_removes_all_product_links_and_allows_recreate():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    PizzaGlobalCrust.__table__.create(engine)
    ProductCrustType.__table__.create(engine)
    context = TenantContext(tenant_id="tenant-a", source=TenantSource.JOB)
    with Session(engine) as db:
        border = _create(
            db, PizzaGlobalCrust,
            GlobalCatalogCreate(name="Cheddar", price_addition=14),
            context, "global-crust",
        )
        db.add(ProductCrustType(
            id="historical-link", tenant_id="tenant-a", product_id="product-a",
            global_crust_id=border.id, name="Cheddar", option_kind="border",
            price_addition=14, active=False,
        ))
        db.commit()

        _delete(db, PizzaGlobalCrust, border.id, context, physical=True)
        assert db.get(PizzaGlobalCrust, border.id) is None
        assert db.get(ProductCrustType, "historical-link") is None

        recreated = _create(
            db, PizzaGlobalCrust,
            GlobalCatalogCreate(name="Cheddar", price_addition=16),
            context, "global-crust",
        )
        db.add(ProductCrustType(
            id="active-link", tenant_id="tenant-a", product_id="product-a",
            global_crust_id=recreated.id, name="Cheddar", option_kind="border",
            price_addition=16, active=True,
        ))
        db.commit()

        _delete(db, PizzaGlobalCrust, recreated.id, context, physical=True)
        assert db.get(PizzaGlobalCrust, recreated.id) is None
        assert db.get(ProductCrustType, "active-link") is None

        recreated_again = _create(
            db, PizzaGlobalCrust,
            GlobalCatalogCreate(name="Cheddar", price_addition=18),
            context, "global-crust",
        )
        assert recreated_again.id not in {border.id, recreated.id}
    engine.dispose()
