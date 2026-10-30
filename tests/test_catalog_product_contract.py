"""Focused backend contracts for category/product/crust catalog support."""
from __future__ import annotations

import importlib.util
from io import StringIO
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError

from backend.models.product import ProductCrustType
from backend.schemas.product import (
    ProductCategoryCreate,
    ProductCreate,
    ProductCrustTypeCreate,
    ProductCrustTypeUpdate,
    ProductUpdate,
)
from backend.services.product_catalog_service import ProductCatalogService


ROOT = Path(__file__).parents[1]
REVISION = "20261029_catalog_product_contract"


def _migration():
    path = ROOT / "backend/migrations/versions" / f"{REVISION}.py"
    spec = importlib.util.spec_from_file_location(REVISION, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_esfiha_is_a_supported_product_type_with_type_specific_default_icon():
    body = ProductCreate(name="Esfiha de carne", description="", price=9, product_type="esfiha")
    values = ProductCatalogService(None, None).product_values(body.model_dump(), creating=True)
    assert values["product_type"] == "esfiha"
    assert values["icon"] == "🥟"
    assert ProductUpdate(product_type="esfiha").product_type == "esfiha"


def test_category_and_crust_order_contracts_reject_negative_values():
    with pytest.raises(ValidationError):
        ProductCategoryCreate(name="Pizzas", sort_order=-1)
    with pytest.raises(ValidationError):
        ProductCrustTypeCreate(name="Catupiry", sort_order=-1)
    with pytest.raises(ValidationError):
        ProductCrustTypeUpdate(price_addition=-0.01)


def test_named_crust_keeps_value_active_and_order_fields():
    assert {"name", "price_addition", "active", "sort_order"}.issubset(ProductCrustType.__table__.columns.keys())
    constraints = {constraint.name for constraint in ProductCrustType.__table__.constraints}
    assert "ck_product_crust_types_price_addition" in constraints
    assert "ck_product_crust_types_sort_order" in constraints


def test_catalog_contract_migration_only_adds_crust_checks():
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    operations = Operations(context)
    with Operations.context(operations.migration_context):
        _migration().upgrade()
    sql = output.getvalue()
    assert "product_crust_types" in sql
    assert "ck_product_crust_types_price_addition" in sql
    assert "ck_product_crust_types_sort_order" in sql
    assert "CREATE TABLE" not in sql
    assert "order_items" not in sql
