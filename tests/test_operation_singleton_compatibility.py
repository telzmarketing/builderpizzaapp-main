"""Compatibility ownership against the complete migrated PostgreSQL schema."""
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.tenant_context import TenantContext, TenantContextMismatch, TenantContextMissing, TenantSource
from backend.core.tenant_route_context import operation_tenant_id
from backend.database import get_db
from backend.main import app as _application  # noqa: F401 - register the complete related model graph
from backend.models.gestao import GestaoModuleSettings
from backend.models.store_operation import StoreOperationSettings
from backend.models.tenant import Tenant
from backend.routes import gestao, store_operation
from backend.services.gestao_service import GestaoService
from backend.services.store_operation_service import StoreOperationService

ROOT = Path(__file__).parents[1]
LEGACY = "tenant-legacy-default"


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    for name in ("MULTI_TENANT_WAVE7_ORM_ENABLED", "TENANT_OPERATIONS_ENFORCEMENT_ENABLED"):
        monkeypatch.setenv(name, "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def migrated_engine():
    url = os.environ.get("OPS_SINGLETON_TEST_DATABASE_URL") or os.environ.get("POSTGRES_RUNTIME_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set OPS_SINGLETON_TEST_DATABASE_URL to a disposable PostgreSQL database")
    admin_engine = sa.create_engine(url, connect_args={"connect_timeout": 5})
    assert admin_engine.dialect.name == "postgresql"
    schema = "operation_singleton_test_" + uuid4().hex
    with admin_engine.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema}", "connect_timeout": 5})
    try:
        env = dict(os.environ, DATABASE_URL=url, PGOPTIONS=f"-csearch_path={schema}",
                   JWT_SECRET_KEY="disposable-operation-test-only")
        result = subprocess.run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stderr[-4000:]
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def db(migrated_engine):
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            for tenant in ("store-a", "store-b"):
                session.add(Tenant(id=tenant, slug=tenant, name=tenant))
            session.add(StoreOperationSettings(id="default", tenant_id=LEGACY,
                        manual_mode="manual_closed", closed_message="Mensagem preservada"))
            session.commit()
            try:
                yield session
            finally:
                transaction.rollback()


def context(tenant_id):
    return TenantContext(tenant_id=tenant_id, source=TenantSource.JOB)


def enable_flags(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE7_ORM_ENABLED", "true")
    monkeypatch.setenv("TENANT_OPERATIONS_ENFORCEMENT_ENABLED", "true")
    get_settings.cache_clear()


def test_operation_compatibility_uses_backfilled_owner_without_enabling_rollout():
    assert operation_tenant_id(None) == LEGACY
    assert operation_tenant_id(context("store-a")) == LEGACY
    support = TenantContext(tenant_id="store-a", source=TenantSource.SUPPORT,
                            actor_id="support", support_session_id="session")
    assert operation_tenant_id(support) == "store-a"


def test_legacy_gestao_seed_is_reused_with_custom_content(db):
    seeded = db.query(GestaoModuleSettings).filter_by(tenant_id=LEGACY).all()
    assert len(seeded) == 4
    inventory = next(row for row in seeded if row.module_key == "inventory")
    assert inventory.id == "gestao-default-inventory"
    inventory.notes = "Notas historicas preservadas"
    inventory.settings_json = '{"negative_stock_policy":"block"}'
    db.commit()
    for legacy_alias in (LEGACY, "default"):
        modules = GestaoService(db, legacy_alias).list_settings()
        actual = next(row for row in modules if row["module_key"] == "inventory")
        assert actual["id"] == inventory.id
        assert actual["notes"] == inventory.notes
        assert actual["settings"]["negative_stock_policy"] == "block"
    assert db.query(GestaoModuleSettings).count() == 4


def test_legacy_store_operation_seed_is_reused(db):
    for legacy_alias in (None, "default", LEGACY):
        service = StoreOperationService(db, legacy_alias)
        settings = service._settings()
        assert settings.id == "default"
        assert settings.tenant_id == LEGACY
        assert settings.closed_message == "Mensagem preservada"
        assert settings.manual_mode == "manual_closed"
    assert db.query(StoreOperationSettings).count() == 1


@pytest.mark.parametrize("enabled", [False, True])
def test_two_explicit_tenants_create_distinct_settings_without_touching_legacy(db, monkeypatch, enabled):
    if enabled:
        enable_flags(monkeypatch)
    ids = set()
    for tenant in ("store-a", "store-b"):
        modules = GestaoService(db, tenant).list_settings()
        assert {row["tenant_id"] for row in modules} == {tenant}
        assert len(modules) == 4
        service = StoreOperationService(db, tenant, context(tenant) if enabled else None)
        settings = service._settings()
        assert settings.tenant_id == tenant
        assert settings.id != "default"
        ids.add(settings.id)
    assert len(ids) == 2
    assert db.query(StoreOperationSettings).filter_by(tenant_id=LEGACY).one().closed_message == "Mensagem preservada"
    assert db.query(StoreOperationSettings).count() == 3
    assert db.query(GestaoModuleSettings).count() == 12


def test_enabled_enforcement_keeps_missing_context_and_mismatch_blocked(db, monkeypatch):
    enable_flags(monkeypatch)
    with pytest.raises(TenantContextMissing):
        operation_tenant_id(None)
    with pytest.raises(TenantContextMissing):
        StoreOperationService(db)
    with pytest.raises(TenantContextMismatch):
        StoreOperationService(db, "store-b", context("store-a"))
    assert operation_tenant_id(context("store-a")) == "store-a"
    assert StoreOperationService(db, tenant_context=context("store-a"))._tenant_id == "store-a"
    assert StoreOperationService(db, "default", context(LEGACY))._settings().id == "default"
    with pytest.raises(TenantContextMismatch):
        StoreOperationService(db, "default", context("store-a"))


@pytest.mark.parametrize("enabled", [False, True])
def test_authenticated_routes_preserve_seed_and_tenant_selection(db, monkeypatch, enabled):
    if enabled:
        enable_flags(monkeypatch)
    app = FastAPI()
    app.include_router(gestao.router, prefix="/api")
    app.include_router(store_operation.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    selected = {"context": context(LEGACY) if enabled else None}
    app.dependency_overrides[gestao.panel_operation_context] = lambda: selected["context"]
    client = TestClient(app)
    assert client.get("/api/gestao/settings").status_code == 401
    assert client.put("/api/gestao/settings/inventory", json={"notes": "unauthorized"}).status_code == 401
    assert client.get("/api/store-operation/config").status_code == 401
    operation_payload = {"manual_mode": "manual_closed", "closed_message": "Mensagem atualizada",
                         "allow_scheduled_orders": False, "timezone": "America/Sao_Paulo"}
    assert client.put("/api/store-operation/settings", json=operation_payload).status_code == 401
    app.dependency_overrides[gestao.get_current_admin] = lambda: SimpleNamespace(id=None, email="admin@example.test")
    response = client.get("/api/gestao/settings")
    assert response.status_code == 200
    assert {row["tenant_id"] for row in response.json()["data"]["modules"]} == {LEGACY}
    response = client.put("/api/gestao/settings/inventory", json={"notes": "Atualizada"})
    assert response.status_code == 200
    assert response.json()["data"]["id"] == "gestao-default-inventory"
    response = client.get("/api/store-operation/config")
    assert response.status_code == 200
    assert response.json()["settings"]["id"] == "default"
    response = client.put("/api/store-operation/settings", json=operation_payload)
    assert response.status_code == 200
    assert response.json()["id"] == "default"
    assert response.json()["closed_message"] == "Mensagem atualizada"
    if enabled:
        selected["context"] = context("store-a")
        response = client.get("/api/gestao/settings")
        assert {row["tenant_id"] for row in response.json()["data"]["modules"]} == {"store-a"}
        response = client.get("/api/store-operation/config")
        assert response.json()["settings"]["tenant_id"] == "store-a"
        assert response.json()["settings"]["id"] != "default"
        assert db.query(GestaoModuleSettings).filter_by(tenant_id=LEGACY, module_key="inventory").one().notes == "Atualizada"
