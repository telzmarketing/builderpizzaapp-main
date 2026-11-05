"""Static contract tests for the additive global catalog backfill."""

import importlib.util
from io import StringIO
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations


ROOT = Path(__file__).parents[1]
PATH = ROOT / "backend/migrations/versions/20261106_product_global_catalog_backfill.py"


def _migration():
    spec = importlib.util.spec_from_file_location("product_global_catalog_backfill", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backfill_is_chained_and_renders_safe_idempotent_sql():
    migration = _migration()
    assert migration.down_revision == "20261106_product_global_links"

    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    operations = Operations(context)
    with Operations.context(operations.migration_context):
        migration.upgrade()
    sql = output.getvalue().lower()

    assert sql.count("insert into pizza_global_sizes") == 1
    assert sql.count("insert into pizza_global_dough_types") == 1
    assert sql.count("insert into pizza_global_crusts") == 1
    assert sql.count("on conflict (tenant_id, name) do nothing") == 3
    assert "md5('pizza_global_sizes:'" in sql
    assert "md5('pizza_global_dough_types:'" in sql
    assert "md5('pizza_global_crusts:'" in sql
    assert "where ps.global_size_id is null" in sql
    assert "where global_dough_type_id is null" in sql
    assert "where global_crust_id is null" in sql
    assert "price_addition_override = case" in sql
    assert "when pct.price_addition <> gc.price_addition" in sql
    assert "delete from" not in sql
    assert "drop table" not in sql


def test_downgrade_is_explicitly_forward_only():
    migration = _migration()
    try:
        migration.downgrade()
    except RuntimeError as exc:
        assert "forward-only" in str(exc).lower()
    else:
        raise AssertionError("backfill downgrade must not silently mutate legacy data")
