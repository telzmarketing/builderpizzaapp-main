"""Execute the additive migration and its integrity gates in an isolated DB."""
from importlib import import_module

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa


@pytest.fixture
def migrated(monkeypatch):
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql("CREATE TABLE tenants (id TEXT PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE orders (id TEXT PRIMARY KEY, tenant_id TEXT, UNIQUE(tenant_id,id))")
        connection.exec_driver_sql("CREATE TABLE production_attempts (id TEXT PRIMARY KEY, tenant_id TEXT, UNIQUE(tenant_id,id))")
        connection.exec_driver_sql("INSERT INTO tenants VALUES ('a'), ('b')")
        connection.exec_driver_sql("INSERT INTO orders VALUES ('order-a','a'), ('order-b','b')")
        connection.exec_driver_sql("INSERT INTO production_attempts VALUES ('attempt-a','a'), ('attempt-b','b')")
        migration = import_module("backend.migrations.versions.20261120_production_effects")
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        yield connection, migration
    engine.dispose()


def insert(connection, **changes):
    row = dict(id="effect", tenant_id="a", kind="loss", business_key="attempt-a",
               idempotency_key="request", request_hash="a" * 64, order_id="order-a",
               attempt_id="attempt-a", source_effect_id=None, actor_id="actor", reason="Queimou",
               cost_total=5, discount_amount=0, snapshot_json="{}")
    row.update(changes)
    connection.execute(sa.text(
        "INSERT INTO production_effects (" + ",".join(row) + ") VALUES (" +
        ",".join(":" + key for key in row) + ")"
    ), row)


def test_additive_upgrade_and_empty_downgrade(migrated):
    connection, migration = migrated
    assert connection.exec_driver_sql("SELECT count(*) FROM orders").scalar() == 2
    migration.downgrade()
    assert "production_effects" not in sa.inspect(connection).get_table_names()
    assert connection.exec_driver_sql("SELECT count(*) FROM orders").scalar() == 2


def test_downgrade_preserves_existing_history(migrated):
    connection, migration = migrated
    insert(connection)
    with pytest.raises(RuntimeError, match="contains history"):
        migration.downgrade()
    assert connection.exec_driver_sql("SELECT count(*) FROM production_effects").scalar() == 1


@pytest.mark.parametrize("changes", [
    {"order_id": "order-b"}, {"attempt_id": "attempt-b"},
    {"request_hash": "short"}, {"cost_total": -1}, {"discount_amount": -1},
    {"reason": " "}, {"kind": "unknown"}, {"kind": "bonification"},
    {"kind": "reproduction"},
])
def test_database_rejects_invalid_effects(migrated, changes):
    connection, _ = migrated
    with pytest.raises(sa.exc.IntegrityError):
        insert(connection, **changes)


@pytest.mark.parametrize("changes", [
    {"idempotency_key": "another"}, {"business_key": "another"},
])
def test_database_enforces_both_business_and_request_identity(migrated, changes):
    connection, _ = migrated
    insert(connection)
    with pytest.raises(sa.exc.IntegrityError):
        insert(connection, id="duplicate", **changes)


def test_source_loss_cannot_cross_tenant(migrated):
    connection, _ = migrated
    insert(connection)
    with pytest.raises(sa.exc.IntegrityError):
        insert(connection, id="foreign-reproduction", tenant_id="b", kind="reproduction",
               order_id="order-b", attempt_id="attempt-b", source_effect_id="effect")
