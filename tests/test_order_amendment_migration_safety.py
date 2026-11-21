"""Verify destructive downgrades fail closed after amendment state exists."""

from importlib import import_module
import io
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
import sqlalchemy as sa


def _run_downgrade(connection, monkeypatch, module_name):
    migration = import_module(module_name)
    monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
    return migration


def test_order_amendment_downgrade_refuses_revision_history(monkeypatch):
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE orders (id TEXT PRIMARY KEY, composition_revision INTEGER NOT NULL)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE order_amendments (id TEXT PRIMARY KEY)"
        )
        connection.exec_driver_sql("INSERT INTO orders VALUES ('order-1', 1)")
        migration = _run_downgrade(
            connection, monkeypatch, "backend.migrations.versions.20261120_order_amendments"
        )
        with pytest.raises(RuntimeError, match="amendment history exists"):
            migration.downgrade()
        assert connection.exec_driver_sql(
            "SELECT composition_revision FROM orders WHERE id = 'order-1'"
        ).scalar() == 1
    engine.dispose()


def test_post_production_amendment_downgrade_refuses_superseded_lines(monkeypatch):
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE order_items (id TEXT PRIMARY KEY, superseded_at DATETIME)"
        )
        connection.exec_driver_sql(
            "INSERT INTO order_items VALUES ('item-1', '2026-11-21 01:00:00')"
        )
        migration = _run_downgrade(
            connection, monkeypatch, "backend.migrations.versions.20261121_post_production_amendment"
        )
        with pytest.raises(RuntimeError, match="superseded history exists"):
            migration.downgrade()
        assert connection.exec_driver_sql(
            "SELECT superseded_at FROM order_items WHERE id = 'item-1'"
        ).scalar() is not None
    engine.dispose()


def test_production_priority_downgrade_refuses_prioritized_attempts(monkeypatch):
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE production_attempts (id TEXT PRIMARY KEY, priority INTEGER NOT NULL)"
        )
        connection.exec_driver_sql("INSERT INTO production_attempts VALUES ('attempt-1', 1)")
        migration = _run_downgrade(
            connection, monkeypatch, "backend.migrations.versions.20261121_post_production_priority"
        )
        with pytest.raises(RuntimeError, match="prioritized work exists"):
            migration.downgrade()
        assert connection.exec_driver_sql(
            "SELECT priority FROM production_attempts WHERE id = 'attempt-1'"
        ).scalar() == 1
    engine.dispose()


def test_order_amendment_sql_enforces_tenant_scoped_idempotency(monkeypatch):
    migration = import_module("backend.migrations.versions.20261120_order_amendments")
    output = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    monkeypatch.setattr(migration, "op", Operations(context))
    migration.upgrade()
    sql = output.getvalue()

    assert "CREATE UNIQUE INDEX uq_idempotency_keys_tenant_id_id" in sql
    assert (
        "CONSTRAINT fk_order_amendments_tenant_idempotency_key "
        "FOREIGN KEY(tenant_id, idempotency_key_id) "
        "REFERENCES idempotency_keys (tenant_id, id)"
    ) in sql
    assert "FOREIGN KEY(idempotency_key_id) REFERENCES idempotency_keys" not in sql


def test_new_objective_migrations_form_one_chain_to_current_head():
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "backend" / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    expected = {
        "20261120_order_amendments": "20261117_combo_landing",
        "20261120_production_effects": "20261120_order_amendments",
        "20261121_post_production_amendment": "20261120_production_effects",
        "20261121_post_production_priority": "20261121_post_production_amendment",
    }
    for revision, down_revision in expected.items():
        assert script.get_revision(revision).down_revision == down_revision

    assert script.get_revision("20261121_payment_amendment_settlement").down_revision == "20261121_post_production_priority"
    assert script.get_heads() == ["20261121_payment_amendment_settlement"]
