"""Focused contracts for additive global-to-product catalog associations."""
from __future__ import annotations

import importlib.util
from io import StringIO
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError

from backend.models.product import ProductCrustType, ProductSize
from backend.schemas.catalog_global import ProductOptionAssociationCreate, ProductSizeAssociationCreate
from backend.schemas.product import ProductCrustTypeOut, ProductSizeOut


ROOT = Path(__file__).parents[1]


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
