"""Contracts for safe operational order removal."""

import importlib.util
from io import StringIO
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations

from backend.core.state_machine import order_sm


ROOT = Path(__file__).parents[1]
REVISION = "20261029_order_operational_archive"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _migration():
    path = ROOT / "backend/migrations/versions" / f"{REVISION}.py"
    spec = importlib.util.spec_from_file_location(REVISION, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pipeline_cancellation_uses_the_existing_order_state_machine():
    for current in ("ready_for_pickup", "on_the_way"):
        assert order_sm.can_transition(current, "cancelled")


def test_archive_migration_is_additive_and_forward_only():
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    operations = Operations(context)
    migration = _migration()
    with Operations.context(operations.migration_context):
        migration.upgrade()
    sql = output.getvalue()
    assert "ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ" in sql
    assert "ADD COLUMN IF NOT EXISTS archived_by VARCHAR(100)" in sql
    assert "ADD COLUMN IF NOT EXISTS archive_reason TEXT" in sql
    assert "ix_orders_tenant_archived_at" in sql
    assert "DROP " not in sql and "DELETE " not in sql and "UPDATE " not in sql

    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    operations = Operations(context)
    with Operations.context(operations.migration_context):
        with pytest.raises(RuntimeError, match="historical order evidence"):
            migration.downgrade()
    assert output.getvalue() == ""


def test_active_queues_exclude_archived_orders_and_delete_is_not_physical():
    kds = _read("backend/services/kds_service.py")
    delivery = _read("backend/services/delivery_service.py")
    board = _read("backend/services/order_board_service.py")
    order = _read("backend/services/order_service.py")
    assert "Order.archived_at.is_(None)" in kds
    assert "Order.archived_at.is_(None)" in delivery
    assert "Order.archived_at.is_(None)" in board
    assert "def archive(" in order
    assert "self._db.delete(order)" not in order
    assert "AdminAuditLog" in order
