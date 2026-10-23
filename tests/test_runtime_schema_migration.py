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
REVISION = "20261017_runtime_schema"
MISSING = {
    "email_templates": {"category": "VARCHAR(50)"},
    "marketing_automations": {"trigger_delay_hours": "INTEGER"},
    "traffic_campaigns": {
        "active_weekdays": "VARCHAR(20)", "pixel_id": "VARCHAR", "pixel_events": "VARCHAR(500)",
    },
}


def load_migration():
    path = ROOT / "backend/migrations/versions" / f"{REVISION}.py"
    spec = importlib.util.spec_from_file_location(REVISION, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_upgrade_only_restores_five_nullable_columns_and_established_defaults():
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    with Operations.context(context):
        load_migration().upgrade()
    sql = output.getvalue()
    statements = [line for line in sql.splitlines() if line.strip()]
    assert len(statements) == 5
    for table, columns in MISSING.items():
        for name, datatype in columns.items():
            assert f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {datatype}" in sql
    assert "category VARCHAR(50) DEFAULT 'marketing'" in sql
    assert "trigger_delay_hours INTEGER DEFAULT 0" in sql
    assert all("DEFAULT" not in line for line in statements if "traffic_campaigns" in line)
    assert not any(token in sql.upper() for token in (
        "NOT NULL", "UPDATE ", "INSERT ", "DELETE ", "DROP ", "TRUNCATE ",
        "ALTER COLUMN", "CREATE TABLE", "CONSTRAINT",
    ))


def test_downgrade_refuses_to_discard_marketing_configuration():
    with pytest.raises(RuntimeError, match="marketing configuration must be preserved"):
        load_migration().downgrade()


def test_runtime_revision_is_the_single_head_after_delivery_schema():
    scripts = ScriptDirectory(str(ROOT / "backend/migrations"))
    assert scripts.get_heads() == ["20261022_receipt_pdf_camera_evidence"]
    assert scripts.get_revision("20261020_product_order_options").down_revision == REVISION
    assert scripts.get_revision(REVISION).down_revision == "20261017_delivery_schema"


@pytest.fixture
def postgres_connection():
    """Explicit test database, isolated temporary schema, rolled back after each test."""
    url = os.environ.get("RUNTIME_SCHEMA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RUNTIME_SCHEMA_TEST_DATABASE_URL to a disposable PostgreSQL database")
    engine = sa.create_engine(url, connect_args={"connect_timeout": 5})
    assert engine.dialect.name == "postgresql"
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                schema = f"runtime_schema_test_{uuid4().hex}"
                connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
                yield connection
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def runtime_tables():
    from backend.routes.email_marketing import EmailTemplate
    from backend.routes.automations import MarketingAutomation
    from backend.models.paid_traffic import TrafficCampaign
    return {model.__tablename__: model.__table__ for model in (
        EmailTemplate, MarketingAutomation, TrafficCampaign,
    )}


def create_previous_shape(connection, *, existing_columns=False, omitted_table=None):
    # Mirror every runtime column, removing only the five omissions proven by
    # the full Alembic-chain PostgreSQL audit. Foreign keys are irrelevant to
    # this isolated additive-column test and are covered by the full-chain gate.
    metadata = sa.MetaData()
    tables = runtime_tables()
    for name, runtime in tables.items():
        if name == omitted_table:
            continue
        columns = [sa.Column(
            column.name, column.type, nullable=column.nullable,
            primary_key=column.primary_key,
        ) for column in runtime.columns
            if existing_columns or column.name not in MISSING[name]]
        sa.Table(name, metadata, *columns)
    metadata.create_all(connection)
    return tables


def upgrade_on(connection):
    with Operations.context(MigrationContext.configure(connection)):
        load_migration().upgrade()


@pytest.mark.parametrize("existing_columns", [False, True])
def test_postgresql_full_models_work_and_existing_values_are_preserved(postgres_connection, existing_columns):
    connection = postgres_connection
    tables = create_previous_shape(connection, existing_columns=existing_columns)
    records = {
        "email_templates": {
            "id": "email-template", "tenant_id": "tenant-test", "name": "Custom Template",
            "subject": "Subject", "body_html": "<p>Keep template</p>",
        },
        "marketing_automations": {
            "id": "automation", "tenant_id": "tenant-test", "name": "Custom Automation",
            "trigger": "order_created", "channel": "email", "trigger_config_json": "{}",
            "conditions_json": "[]", "actions_json": "[]",
        },
        "traffic_campaigns": {
            "id": "traffic", "tenant_id": "tenant-test", "name": "Custom Traffic",
            "platform": "manual", "status": "draft", "daily_budget": 17.5,
        },
    }
    if existing_columns:
        records["email_templates"]["category"] = "transactional"
        records["marketing_automations"]["trigger_delay_hours"] = 12
        records["traffic_campaigns"].update({
            "active_weekdays": "1,3,5", "pixel_id": "custom-pixel", "pixel_events": "Purchase",
        })
    for name, record in records.items():
        # Reflect only the previous shape so no omitted column appears in INSERT.
        previous = sa.Table(name, sa.MetaData(), autoload_with=connection)
        connection.execute(previous.insert().values(**record))
    upgrade_on(connection)
    upgrade_on(connection)
    for name, runtime in tables.items():
        row = connection.execute(runtime.select()).mappings().one()
        assert all(row[key] == value for key, value in records[name].items())
        reflected = {column["name"]: column for column in sa.inspect(connection).get_columns(name)}
        assert set(reflected) == set(runtime.columns.keys())
        for field, datatype in MISSING[name].items():
            assert reflected[field]["nullable"]
            assert str(reflected[field]["type"]) == datatype
            if not existing_columns:
                if field == "category":
                    assert row[field] == "marketing"
                    assert "marketing" in reflected[field]["default"]
                elif field == "trigger_delay_hours":
                    assert row[field] == 0
                    assert reflected[field]["default"] == "0"
                else:
                    assert row[field] is None
                    assert reflected[field]["default"] is None
            else:
                # Existing per-installation column defaults are not overwritten.
                assert reflected[field]["default"] is None


@pytest.mark.parametrize("omitted_table", list(MISSING))
def test_postgresql_missing_base_table_fails_without_creating_it(postgres_connection, omitted_table):
    connection = postgres_connection
    create_previous_shape(connection, omitted_table=omitted_table)
    with pytest.raises(sa.exc.ProgrammingError):
        with connection.begin_nested():
            upgrade_on(connection)
    assert connection.execute(sa.text("SELECT to_regclass(:table)"), {"table": omitted_table}).scalar() is None
