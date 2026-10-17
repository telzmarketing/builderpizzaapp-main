import importlib.util
import json
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
REVISION = "20261017_site_config"


def load_migration():
    path = ROOT / "backend/migrations/versions" / f"{REVISION}.py"
    spec = importlib.util.spec_from_file_location(REVISION, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_upgrade_preserves_legacy_schema_and_existing_content():
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    with Operations.context(context):
        load_migration().upgrade()
    sql = output.getvalue()
    assert "CREATE TABLE IF NOT EXISTS site_config" in sql
    assert "id VARCHAR PRIMARY KEY DEFAULT 'default'" in sql
    assert "content TEXT NOT NULL DEFAULT '{}'" in sql
    assert "updated_at TIMESTAMPTZ DEFAULT NOW()" in sql
    assert "VALUES ('default', '{}') ON CONFLICT (id) DO NOTHING" in sql
    assert not any(token in sql for token in ("DROP ", "DELETE ", "UPDATE ", "TRUNCATE "))


def test_downgrade_refuses_to_destroy_settings():
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    with Operations.context(context):
        with pytest.raises(RuntimeError, match="settings must be preserved"):
            load_migration().downgrade()
    assert output.getvalue() == ""


def test_revision_follows_domain_ssl_in_canonical_history():
    scripts = ScriptDirectory(str(ROOT / "backend/migrations"))
    assert REVISION in {revision.revision for revision in scripts.walk_revisions()}
    assert scripts.get_revision(REVISION).down_revision == "20261014_tenant_domain_ssl"


@pytest.fixture
def postgres_connection():
    """Opt-in real PostgreSQL check in a transactionally isolated test schema."""
    url = os.environ.get("SITE_CONFIG_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set SITE_CONFIG_TEST_DATABASE_URL to a disposable PostgreSQL database")
    engine = sa.create_engine(url, connect_args={"connect_timeout": 5})
    assert engine.dialect.name == "postgresql"
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                schema = f"site_config_test_{uuid4().hex}"
                connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
                yield connection
            finally:
                # Includes CREATE SCHEMA, all DDL and any inserted configuration.
                transaction.rollback()
    finally:
        engine.dispose()


def upgrade_on(connection):
    with Operations.context(MigrationContext.configure(connection)):
        load_migration().upgrade()


def test_postgresql_routes_read_configuration_after_upgrade(postgres_connection):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session

    from backend.database import get_db
    from backend.routes.site_config import router

    upgrade_on(postgres_connection)
    app = FastAPI()
    app.include_router(router, prefix="/api")
    with Session(bind=postgres_connection) as session:
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        response = client.get("/api/site-config")
        assert response.status_code == 200
        assert response.json()["data"] == {}
        favicon = client.get("/api/site-config/favicon?size=32", follow_redirects=False)
        assert favicon.status_code == 307
        assert favicon.headers["location"].startswith("/icons/favicon-moschettieri-32.png?v=")

        branding = {"brand": {"name": "Loja", "faviconUrl": "/uploads/custom.png"}}
        postgres_connection.execute(sa.text(
            "UPDATE site_config SET content = :content WHERE id = 'default'"
        ), {"content": json.dumps(branding)})
        assert client.get("/api/site-config").json()["data"] == branding
        favicon = client.get("/api/site-config/favicon?size=32", follow_redirects=False)
        assert favicon.status_code == 307
        assert favicon.headers["location"].startswith("/uploads/custom.png?v=")


def test_postgresql_missing_table_is_created_seeded_and_repeatable(postgres_connection):
    connection = postgres_connection
    upgrade_on(connection)
    upgrade_on(connection)
    row = connection.execute(sa.text("SELECT id, content, updated_at FROM site_config")).one()
    assert row.id == "default"
    assert json.loads(row.content) == {}
    assert row.updated_at.tzinfo is not None
    columns = {column["name"]: column for column in sa.inspect(connection).get_columns("site_config")}
    assert set(columns) == {"id", "content", "updated_at"}
    assert not columns["id"]["nullable"]
    assert not columns["content"]["nullable"]
    assert columns["updated_at"]["nullable"]
    assert columns["updated_at"]["type"].timezone
    assert sa.inspect(connection).get_pk_constraint("site_config")["constrained_columns"] == ["id"]
    with pytest.raises(sa.exc.IntegrityError):
        with connection.begin_nested():
            connection.execute(sa.text("INSERT INTO site_config (id, content) VALUES ('invalid', NULL)"))


@pytest.mark.parametrize("has_default", [False, True])
def test_postgresql_bootstrap_table_keeps_customized_rows(postgres_connection, has_default):
    connection = postgres_connection
    # Exact DDL from the pre-migration startup bootstrap, including nullable timestamp.
    connection.execute(sa.text(
        "CREATE TABLE site_config (id VARCHAR PRIMARY KEY DEFAULT 'default', "
        "content TEXT NOT NULL DEFAULT '{}', updated_at TIMESTAMPTZ DEFAULT NOW())"
    ))
    content = '{"brand":{"name":"Loja personalizada","faviconUrl":"/uploads/custom.png"}}'
    ids = ["legacy", "default"] if has_default else ["legacy"]
    for identifier in ids:
        connection.execute(sa.text(
            "INSERT INTO site_config (id, content, updated_at) "
            "VALUES (:id, :content, '2026-01-01T00:00:00Z')"
        ), {"id": identifier, "content": content})
    before = connection.execute(sa.text(
        "SELECT id, content, updated_at FROM site_config ORDER BY id"
    )).all()
    upgrade_on(connection)
    upgrade_on(connection)
    after = connection.execute(sa.text(
        "SELECT id, content, updated_at FROM site_config ORDER BY id"
    )).all()
    assert all(row in after for row in before)
    assert len(after) == 2
    if not has_default:
        assert json.loads(after[0].content) == {}
