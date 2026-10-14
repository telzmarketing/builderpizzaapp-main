import importlib.util
from io import StringIO
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory


ROOT = Path(__file__).parents[1]
REVISION = "20261014_order_cancellation_tracking"


def load_migration():
    path = ROOT / "backend/migrations/versions" / f"{REVISION}.py"
    spec = importlib.util.spec_from_file_location(REVISION, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def offline_operations():
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    return Operations(context), output


def test_upgrade_emits_guarded_nullable_postgresql_columns_and_partial_index():
    migration = load_migration()
    operations, output = offline_operations()
    with Operations.context(operations.migration_context):
        migration.upgrade()
    sql = output.getvalue()

    for definition in (
        "cancelled_by VARCHAR(50)",
        "cancellation_reason TEXT",
        "cancelled_at TIMESTAMPTZ",
    ):
        assert f"ADD COLUMN IF NOT EXISTS {definition}" in sql
    assert (
        "CREATE INDEX IF NOT EXISTS idx_orders_cancelled_by "
        "ON orders (cancelled_by) WHERE cancelled_by IS NOT NULL"
    ) in sql
    for destructive_or_backfill in ("DROP ", "UPDATE ", "DELETE ", "NOT NULL,", "DEFAULT "):
        assert destructive_or_backfill not in sql


def test_downgrade_blocks_before_emitting_any_sql():
    migration = load_migration()
    operations, output = offline_operations()
    with Operations.context(operations.migration_context):
        with pytest.raises(RuntimeError, match="history must be preserved"):
            migration.downgrade()
    assert output.getvalue() == ""


def test_cancellation_revision_is_single_head_after_upload_ownership():
    script = ScriptDirectory(str(ROOT / "backend/migrations"))
    assert script.get_heads() == [REVISION]
    assert script.get_revision(REVISION).down_revision == (
        "20261004_tenant_upload_ownership_contract"
    )
