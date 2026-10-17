"""Real session regressions for migrated legacy singletons and tenant isolation."""
import os
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Query, Session

from backend.core import wave6_tenant_context
from backend.core.tenant_context import TenantContext, TenantSource
from backend.database import get_db
from backend.models.exit_popup import ExitPopupConfig
from backend.routes import exit_popup
from backend.services.exit_popup_service import ExitPopupService


@pytest.fixture(params=["sqlite", "postgresql"])
def connection(request):
    url = os.environ.get("POPUP_TEST_DATABASE_URL")
    if request.param == "postgresql" and not url:
        pytest.skip("Set POPUP_TEST_DATABASE_URL to a disposable PostgreSQL database")
    engine = sa.create_engine(url if request.param == "postgresql" else "sqlite://",
                              connect_args={} if request.param == "postgresql" else {"check_same_thread": False})
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            if request.param == "postgresql":
                schema = "popup_test_" + uuid4().hex
                conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
                conn.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
                # The fixture needs only the ownership FK target, not the full SaaS schema.
                conn.execute(sa.text("CREATE TABLE tenants (id VARCHAR PRIMARY KEY)"))
                for tenant in ("tenant-legacy-default", "store-a", "store-b"):
                    conn.execute(sa.text("INSERT INTO tenants (id) VALUES (:id)"), {"id": tenant})
            ExitPopupConfig.__table__.create(conn)
            # Production's partial unique index is declared by tenant ORM metadata.
            yield conn
        finally:
            transaction.rollback()
    engine.dispose()


@pytest.fixture
def api(connection, monkeypatch):
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    app = FastAPI()
    app.include_router(exit_popup.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: session
    tenant = {"id": "tenant-legacy-default"}

    def context():
        return TenantContext(tenant_id=tenant["id"], source=TenantSource.PUBLIC_HOST,
                             hostname="test.example.com")

    app.dependency_overrides[exit_popup.public_wave6_context] = context
    app.dependency_overrides[exit_popup.panel_wave6_context] = context
    monkeypatch.setattr(wave6_tenant_context, "wave6_tenant_orm_enabled", lambda: True)
    try:
        yield TestClient(app), app, session, tenant
    finally:
        session.close()


def test_legacy_seed_is_read_and_updated_without_new_id(api):
    client, app, session, tenant = api
    session.add(ExitPopupConfig(id="default", tenant_id=tenant["id"], enabled=True,
                                title="Minha oferta", coupon_code="LEGADO"))
    session.commit()
    response = client.get("/api/exit-popup")
    assert response.status_code == 200
    assert response.json()["id"] == "default"
    assert response.json()["coupon_code"] == "LEGADO"
    assert client.put("/api/exit-popup", json={"title": "Alterada"}).status_code == 401
    app.dependency_overrides[exit_popup.get_current_admin] = lambda: object()
    response = client.put("/api/exit-popup", json={"title": "Alterada", "trigger_delay_seconds": 0})
    assert response.status_code == 200
    assert response.json()["id"] == "default"
    assert response.json()["title"] == "Alterada"
    assert response.json()["coupon_code"] == "LEGADO"
    assert response.json()["trigger_delay_seconds"] == 1
    assert session.query(ExitPopupConfig).count() == 1


def test_new_tenant_singleton_and_update_are_isolated(api):
    client, app, session, tenant = api
    session.add(ExitPopupConfig(id="default", tenant_id="tenant-legacy-default", title="Legacy"))
    session.add(ExitPopupConfig(id="custom-b", tenant_id="store-b", title="B"))
    session.commit()
    tenant["id"] = "store-a"
    created = client.get("/api/exit-popup")
    assert created.status_code == 200
    assert created.json()["id"] == "exit-popup-store-a"
    assert created.json()["enabled"] is False
    assert client.get("/api/exit-popup").json()["id"] == created.json()["id"]
    app.dependency_overrides[exit_popup.get_current_admin] = lambda: object()
    assert client.put("/api/exit-popup", json={"title": "A"}).status_code == 200
    tenant["id"] = "store-b"
    assert client.get("/api/exit-popup").json()["title"] == "B"
    assert client.get("/api/exit-popup").json()["id"] == "custom-b"
    tenant["id"] = "tenant-legacy-default"
    assert client.get("/api/exit-popup").json()["title"] == "Legacy"
    assert session.query(ExitPopupConfig).count() == 3


def test_compatibility_mode_finds_backfilled_default(api, monkeypatch):
    client, _, session, _ = api
    monkeypatch.setattr(wave6_tenant_context, "wave6_tenant_orm_enabled", lambda: False)
    session.add(ExitPopupConfig(id="default", tenant_id="tenant-legacy-default", title="Preservada"))
    session.commit()
    assert client.get("/api/exit-popup").json()["title"] == "Preservada"
    assert session.query(ExitPopupConfig).count() == 1


def test_primary_key_owned_by_another_tenant_is_not_recovered(api):
    _, _, session, _ = api
    session.add(ExitPopupConfig(id="exit-popup-store-a", tenant_id="store-b"))
    session.commit()
    with pytest.raises(sa.exc.IntegrityError):
        ExitPopupService(session).get_or_create("store-a")
    assert session.query(ExitPopupConfig).filter_by(tenant_id="store-a").count() == 0


def test_stale_initial_read_recovers_database_unique_collision(api, monkeypatch):
    _, _, session, _ = api
    session.add(ExitPopupConfig(id="winner-existing-id", tenant_id="store-a", title="Winner"))
    session.commit()
    original = Query.one_or_none
    reads = []

    def stale_first_read(query):
        reads.append(True)
        return None if len(reads) == 1 else original(query)

    # Model the interleaving where the first read precedes a competing commit.
    # The INSERT and its unique violation are executed against the real database.
    monkeypatch.setattr(Query, "one_or_none", stale_first_read)
    recovered = ExitPopupService(session).get_or_create("store-a")
    assert recovered.id == "winner-existing-id"
    assert recovered.title == "Winner"
    assert len(reads) == 2
    assert session.query(ExitPopupConfig).count() == 1


def test_unrelated_integrity_error_is_not_hidden_by_existing_singleton(api, connection, monkeypatch):
    _, _, session, _ = api
    session.add(ExitPopupConfig(id="winner-existing-id", tenant_id="store-a"))
    session.commit()
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text("ALTER TABLE exit_popup_config ADD CONSTRAINT popup_test_failure "
                                   "CHECK (id <> 'exit-popup-store-a')"))
    else:
        connection.execute(sa.text("CREATE TRIGGER popup_test_failure BEFORE INSERT ON exit_popup_config "
                                   "WHEN NEW.id = 'exit-popup-store-a' BEGIN "
                                   "SELECT RAISE(ABORT, 'popup_test_failure'); END"))
    reads = []

    def stale_read(query):
        reads.append(True)
        return None

    monkeypatch.setattr(Query, "one_or_none", stale_read)
    with pytest.raises(sa.exc.IntegrityError, match="popup_test_failure"):
        ExitPopupService(session).get_or_create("store-a")
    assert len(reads) == 1
