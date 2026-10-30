"""Typed catalog options: real SQL persistence and HTTP contracts on isolated SQLite.

PostgreSQL migration execution is covered by the opt-in catalog audit suite;
offline SQL checks below validate the forward-only DDL without a live server.
"""
import importlib.util
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.main import app as registered_app  # noqa: F401 - complete ORM registry
from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext, TenantSource
from backend.database import get_db
from backend.models.product import Product, ProductCategory, ProductCrustType
from backend.routes import products
from backend.routes.admin_auth import get_current_admin
from backend.schemas.product import ProductCrustTypeCreate, ProductCrustTypeUpdate
from backend.services.product_pricing_service import ProductPricingService


@pytest.fixture
def catalog(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    for model in (ProductCategory, Product, ProductCrustType):
        model.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as db:
        category = ProductCategory(id="cat", tenant_id="tenant-a", name="Food", enable_dough=True, enable_border=True)
        product = Product(id="pizza", tenant_id="tenant-a", category_id="cat", name="Pizza", description="", price=30, promotions=[])
        db.add_all([category, product])
        db.commit()
        context = TenantContext(tenant_id="tenant-a", source=TenantSource.JOB)
        monkeypatch.setattr(products, "resolve_public_tenant_context", lambda *_: context)
        monkeypatch.setattr(products, "resolve_panel_tenant_context", lambda *_: context)
        monkeypatch.setattr(products, "_require_catalog_admin", lambda *_: True)
        app = FastAPI()
        app.include_router(products.router, prefix="/api")
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id="admin")
        # Authentication/RBAC is tested separately; exercise the actual handlers,
        # services, schemas and tenant-scoped SQL without requiring membership tables.
        for route in products.router.routes:
            for dependency in route.dependencies:
                app.dependency_overrides[dependency.dependency] = lambda: True
        with TestClient(app) as client:
            yield SimpleNamespace(db=db, client=client, category=category, product=product)
    engine.dispose()


def create(state, **values):
    return state.client.post("/api/products/pizza/crusts", json={"name": "Arbitrary", **values})


def test_legacy_default_and_explicit_reclassification_preserve_id(catalog):
    response = create(catalog, name="Borda de Catupiry")
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["option_kind"] == "dough"  # never infer from display name
    response = catalog.client.put(f"/api/products/pizza/crusts/{row['id']}", json={"option_kind": "border"})
    assert response.status_code == 200, response.text
    assert response.json()["id"] == row["id"]
    assert response.json()["option_kind"] == "border"
    response = catalog.client.put(f"/api/products/pizza/crusts/{row['id']}", json={"name": "Tradicional"})
    assert response.json()["option_kind"] == "border"


@pytest.mark.parametrize("kind,disabled", [("dough", "enable_dough"), ("border", "enable_border")])
def test_create_update_and_public_list_respect_independent_capabilities(catalog, kind, disabled):
    row = create(catalog, option_kind=kind).json()
    setattr(catalog.category, disabled, False)
    catalog.db.commit()
    assert create(catalog, option_kind=kind).status_code == 422
    quote_param = "crust_id" if kind == "dough" else "border_id"
    assert catalog.client.get("/api/products/pizza/price", params={quote_param: row["id"]}).status_code == 422
    assert catalog.client.put(f"/api/products/pizza/crusts/{row['id']}", json={"price_addition": 5}).status_code == 422
    assert catalog.client.get("/api/products/pizza/crusts", params={"option_kind": kind}).json() == []
    # Admin can still inspect disabled options to prepare an explicit correction.
    response = catalog.client.get("/api/products/pizza/crusts", params={"option_kind": kind, "active_only": "false"})
    assert [item["id"] for item in response.json()] == [row["id"]]
    other_kind = "border" if kind == "dough" else "dough"
    assert create(catalog, option_kind=other_kind).status_code == 201
    response = catalog.client.put(f"/api/products/pizza/crusts/{row['id']}", json={"option_kind": other_kind})
    assert response.status_code == 200


def test_lists_filter_kind_active_product_and_tenant(catalog):
    dough = create(catalog).json()
    border = create(catalog, option_kind="border").json()
    create(catalog, option_kind="border", active=False)
    catalog.db.add(ProductCrustType(id="foreign", tenant_id="tenant-b", product_id="pizza", name="Other", option_kind="border"))
    catalog.db.commit()
    assert {row["id"] for row in catalog.client.get("/api/products/pizza/crusts").json()} == {dough["id"], border["id"]}
    assert [row["id"] for row in catalog.client.get("/api/products/pizza/crusts?option_kind=dough").json()] == [dough["id"]]
    assert [row["id"] for row in catalog.client.get("/api/products/pizza/crusts?option_kind=border").json()] == [border["id"]]
    assert catalog.client.get("/api/products/pizza/crusts?option_kind=invalid").status_code == 422
    assert catalog.client.put("/api/products/pizza/crusts/foreign", json={"option_kind": "dough"}).status_code == 404
    catalog.product.visible_delivery = False
    catalog.db.commit()
    assert catalog.client.get("/api/products/pizza/crusts").status_code == 404
    assert catalog.client.get("/api/products/missing/crusts").status_code == 404


@pytest.mark.parametrize("kind", [None, "invalid", "", 1])
def test_schemas_reject_invalid_explicit_kind(kind):
    for schema in (ProductCrustTypeCreate, ProductCrustTypeUpdate):
        with pytest.raises(ValidationError):
            schema(name="Option", option_kind=kind)


def test_database_default_and_check_constraint(catalog):
    catalog.db.execute(text("INSERT INTO product_crust_types (id, product_id, name) VALUES ('legacy', 'pizza', 'Borda')"))
    assert catalog.db.execute(text("SELECT option_kind FROM product_crust_types WHERE id='legacy'")).scalar_one() == "dough"
    with pytest.raises(IntegrityError):
        catalog.db.execute(text("UPDATE product_crust_types SET option_kind='invalid' WHERE id='legacy'"))
    catalog.db.rollback()


@pytest.mark.parametrize("kind,param,status", [("border", "crust_id", 404), ("dough", "border_id", 422)])
def test_quote_rejects_wrong_kind_before_pricing(catalog, kind, param, status):
    row = create(catalog, option_kind=kind).json()
    response = catalog.client.get("/api/products/pizza/price", params={param: row["id"]})
    assert response.status_code == status, response.text


def test_quote_accepts_distinct_typed_options_and_uses_stored_prices(catalog):
    dough = create(catalog, name="Borda is just a display name", price_addition=2).json()
    border = create(catalog, name="Tradicional", option_kind="border", price_addition=7).json()
    response = catalog.client.get("/api/products/pizza/price", params={"crust_id": dough["id"], "border_id": border["id"]})
    assert response.status_code == 200, response.text
    assert response.json()["final_price"] == 39
    catalog.db.get(ProductCrustType, border["id"]).active = False
    catalog.db.commit()
    assert catalog.client.get("/api/products/pizza/price", params={"border_id": border["id"]}).status_code == 422


def test_api_rejects_explicit_null_and_unknown_kind(catalog):
    row = create(catalog).json()
    for kind in (None, "unknown"):
        assert create(catalog, option_kind=kind).status_code == 422
        response = catalog.client.put(f"/api/products/pizza/crusts/{row['id']}", json={"option_kind": kind})
        assert response.status_code == 422


@pytest.mark.parametrize("slot,kind", [("crust", "border"), ("border", "dough")])
def test_pricing_service_rejects_wrong_kind(slot, kind):
    with pytest.raises(DomainError) as error:
        ProductPricingService(None).calculate(product=None, **{slot: SimpleNamespace(option_kind=kind)})
    assert error.value.code == "InvalidProductOptionKind"


def test_forward_only_migration_sql():
    path = Path(__file__).parents[1] / "backend/migrations/versions/20261030_crust_option_kind.py"
    spec = importlib.util.spec_from_file_location("crust_kind_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    output = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
    with Operations.context(context):
        migration.upgrade()
    sql = output.getvalue()
    assert "DEFAULT 'dough' NOT NULL" in sql
    assert "CHECK (option_kind IN ('dough', 'border'))" in sql
    assert "UPDATE " not in sql and "DELETE " not in sql and "DROP " not in sql
    with pytest.raises(RuntimeError, match="Forward-only"):
        migration.downgrade()
