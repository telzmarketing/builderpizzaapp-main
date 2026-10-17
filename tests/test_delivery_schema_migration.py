import importlib.util
import os
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory


ROOT = Path(__file__).parents[1]
REVISION = "20261017_delivery_schema"
COLUMNS = {
    "password_hash": "TEXT",
    "cpf": "VARCHAR(14)",
    "cnh": "VARCHAR(20)",
    "pix_key": "VARCHAR(200)",
}


def load_migration(revision=REVISION):
    path = ROOT / "backend/migrations/versions" / f"{revision}.py"
    spec = importlib.util.spec_from_file_location(revision, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_upgrade_only_adds_existing_runtime_contract_columns():
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    with Operations.context(context):
        load_migration().upgrade()
    sql = output.getvalue()
    for name, datatype in COLUMNS.items():
        assert f"ALTER TABLE delivery_persons ADD COLUMN IF NOT EXISTS {name} {datatype};" in sql
    assert "ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS confirmation_code VARCHAR(4);" in sql
    assert "ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS confirmed_by_code_at TIMESTAMPTZ;" in sql
    assert "ALTER TABLE logistics_settings ADD COLUMN IF NOT EXISTS rate_per_delivery FLOAT DEFAULT 0.0;" in sql
    statements = [line for line in sql.splitlines() if line.strip()]
    assert len(statements) == 7
    assert all("DEFAULT" not in line for line in statements if "logistics_settings" not in line)
    assert not any(token in sql.upper() for token in (
        "NOT NULL", "UPDATE ", "INSERT ", "DELETE ", "DROP ", "TRUNCATE "
    ))


def test_downgrade_preserves_credentials_and_documents():
    with pytest.raises(RuntimeError, match="confirmations must be preserved"):
        load_migration().downgrade()


def test_revision_follows_site_config_and_keeps_single_head():
    scripts = ScriptDirectory(str(ROOT / "backend/migrations"))
    assert scripts.get_heads() == [REVISION]
    assert scripts.get_revision(REVISION).down_revision == "20261017_site_config"


@pytest.fixture
def postgres_connection():
    """Only touch an isolated temporary schema in an explicitly selected test DB."""
    url = os.environ.get("DRIVER_SCHEMA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set DRIVER_SCHEMA_TEST_DATABASE_URL to a disposable PostgreSQL database")
    engine = sa.create_engine(url, connect_args={"connect_timeout": 5})
    assert engine.dialect.name == "postgresql"
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                schema = f"driver_auth_test_{uuid4().hex}"
                connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
                yield connection
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def upgrade_on(connection):
    with Operations.context(MigrationContext.configure(connection)):
        load_migration().upgrade()


def create_other_domain_tables(connection):
    connection.execute(sa.text("CREATE TABLE deliveries (id VARCHAR PRIMARY KEY)"))
    connection.execute(sa.text("CREATE TABLE logistics_settings (id VARCHAR PRIMARY KEY)"))


def test_postgresql_restores_full_driver_projection_from_historical_schema(postgres_connection):
    connection = postgres_connection
    create_other_domain_tables(connection)
    # Authoritative original DDL, then the historical email/tenant/deleted_at additions.
    baseline = load_migration("20260422_initial_schema")._statements()
    for sql in baseline:
        if sql.startswith(("CREATE TYPE vehicletype ", "CREATE TYPE deliverypersonstatus ",
                           "CREATE TABLE delivery_persons ")):
            connection.execute(sa.text(sql))
    connection.execute(sa.text("ALTER TABLE delivery_persons ADD COLUMN email VARCHAR(200)"))
    connection.execute(sa.text("ALTER TABLE delivery_persons ADD COLUMN tenant_id VARCHAR NOT NULL"))
    connection.execute(sa.text("ALTER TABLE delivery_persons ADD COLUMN deleted_at TIMESTAMPTZ"))
    connection.execute(sa.text(
        "INSERT INTO delivery_persons (id, name, phone, tenant_id) "
        "VALUES ('driver-legacy', 'Legacy Driver', '11999990000', 'tenant-test')"
    ))
    upgrade_on(connection)
    upgrade_on(connection)

    # Selecting the complete mapped table detects the next omitted model column.
    from backend.models.delivery import DeliveryPerson
    row = connection.execute(DeliveryPerson.__table__.select()).mappings().one()
    assert row["id"] == "driver-legacy"
    assert all(row[name] is None for name in COLUMNS)
    columns = {column["name"]: column for column in sa.inspect(connection).get_columns("delivery_persons")}
    assert set(columns) == set(DeliveryPerson.__table__.columns.keys())
    for name, datatype in COLUMNS.items():
        assert columns[name]["nullable"]
        assert columns[name]["default"] is None
        assert str(columns[name]["type"]) == datatype


def test_postgresql_preserves_existing_hash_documents_and_unrelated_driver_rows(postgres_connection):
    connection = postgres_connection
    create_other_domain_tables(connection)
    connection.execute(sa.text(
        "CREATE TABLE delivery_persons (id VARCHAR PRIMARY KEY, name VARCHAR(200), "
        "password_hash TEXT, cpf VARCHAR(14), cnh VARCHAR(20), pix_key VARCHAR(200))"
    ))
    connection.execute(sa.text(
        "INSERT INTO delivery_persons VALUES "
        "('driver-custom', 'Custom Driver', '$2b$12$existing_hash', '123.456.789-00', '12345', 'pix@example.test'),"
        "('driver-without-login', 'No Credentials', NULL, NULL, NULL, NULL)"
    ))
    before = connection.execute(sa.text("SELECT * FROM delivery_persons ORDER BY id")).all()
    upgrade_on(connection)
    upgrade_on(connection)
    after = connection.execute(sa.text("SELECT * FROM delivery_persons ORDER BY id")).all()
    assert after == before


def test_postgresql_missing_base_table_fails_without_creating_empty_table(postgres_connection):
    connection = postgres_connection
    with pytest.raises(sa.exc.ProgrammingError):
        with connection.begin_nested():
            upgrade_on(connection)
    assert connection.execute(sa.text("SELECT to_regclass('delivery_persons')")).scalar() is None


def test_postgresql_full_delivery_and_logistics_projection_preserves_runtime_values(postgres_connection):
    connection = postgres_connection
    connection.execute(sa.text("CREATE TABLE orders (id VARCHAR PRIMARY KEY)"))
    connection.execute(sa.text("CREATE TABLE delivery_persons (id VARCHAR PRIMARY KEY)"))
    baseline = load_migration("20260422_initial_schema")._statements()
    for sql in baseline:
        if sql.startswith(("CREATE TYPE deliverystatus ", "CREATE TABLE deliveries ")):
            connection.execute(sa.text(sql))
    for definition in (
        "problem_report TEXT", "problem_reported_at TIMESTAMPTZ",
        "problem_resolved_at TIMESTAMPTZ", "admin_resolution_note TEXT", "tenant_id VARCHAR",
    ):
        connection.execute(sa.text(f"ALTER TABLE deliveries ADD COLUMN {definition}"))
    # Existing settings schema from 20260730_tenant_operations_expand, plus ownership.
    connection.execute(sa.text(
        "CREATE TABLE logistics_settings (id VARCHAR DEFAULT 'default', tenant_id VARCHAR, "
        "auto_assign BOOLEAN DEFAULT FALSE, max_concurrent_deliveries INTEGER DEFAULT 3, "
        "default_estimated_minutes INTEGER DEFAULT 40, confirmation_code_enabled BOOLEAN DEFAULT TRUE, "
        "updated_at TIMESTAMPTZ DEFAULT NOW(), PRIMARY KEY (id, tenant_id))"
    ))
    connection.execute(sa.text("INSERT INTO orders (id) VALUES ('order-legacy')"))
    connection.execute(sa.text(
        "INSERT INTO deliveries (id, order_id, tenant_id, status, notes) "
        "VALUES ('delivery-legacy', 'order-legacy', 'tenant-test', 'assigned', 'preserve')"
    ))
    connection.execute(sa.text(
        "INSERT INTO logistics_settings (id, tenant_id, max_concurrent_deliveries) "
        "VALUES ('default', 'tenant-test', 7)"
    ))
    upgrade_on(connection)
    upgrade_on(connection)
    from backend.models.delivery import Delivery, LogisticsSettings
    row = connection.execute(Delivery.__table__.select()).mappings().one()
    assert row["notes"] == "preserve"
    assert row["status"].value == "assigned"
    assert row["confirmation_code"] is None
    assert row["confirmed_by_code_at"] is None
    columns = {column["name"] for column in sa.inspect(connection).get_columns("deliveries")}
    assert columns == set(Delivery.__table__.columns.keys())
    settings = connection.execute(LogisticsSettings.__table__.select()).mappings().one()
    assert settings["max_concurrent_deliveries"] == 7
    assert settings["rate_per_delivery"] == 0.0
    connection.execute(sa.text(
        "UPDATE deliveries SET confirmation_code = '1234', "
        "confirmed_by_code_at = '2026-10-17T12:00:00Z'"
    ))
    connection.execute(sa.text("UPDATE logistics_settings SET rate_per_delivery = 13.75"))
    before = connection.execute(Delivery.__table__.select()).one()
    before_settings = connection.execute(LogisticsSettings.__table__.select()).one()
    upgrade_on(connection)
    assert connection.execute(Delivery.__table__.select()).one() == before
    assert connection.execute(LogisticsSettings.__table__.select()).one() == before_settings
    for column in sa.inspect(connection).get_columns("deliveries"):
        if column["name"] in {"confirmation_code", "confirmed_by_code_at"}:
            assert column["nullable"] and column["default"] is None
    rate = next(column for column in sa.inspect(connection).get_columns("logistics_settings")
                if column["name"] == "rate_per_delivery")
    assert rate["nullable"] and rate["default"] is not None
