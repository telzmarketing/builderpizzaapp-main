"""HTTP/SQL integration checks for manager and tenant branding boundaries."""
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import get_settings
from backend.core import security
from backend.core.exceptions import DomainError
from backend.database import Base, get_db
from backend.models.admin import AdminUser
from backend.models.membership import TenantMembership
from backend.models.platform_saas import TenantProfile
from backend.models.rbac import Role, RbacModule, RbacPermission, RolePermission, UserPermission
from backend.models.tenant import Tenant
from backend.models.tenant_domain import TenantDomain
from backend.routes.site_config import router


LEGACY = "tenant-legacy-default"
READ_PATHS = ("/api/site-config", "/api/site-config/favicon?size=32", "/api/site-config/manifest.webmanifest")


@pytest.fixture
def branding(monkeypatch):
    for name, value in {
        "TENANT_DOMAINS_ENABLED": "true",
        "MULTI_TENANT_AUTH_ENABLED": "true",
        "TENANT_DOMAINS_PLATFORM_HOSTNAMES": "manager.example.com",
        "TENANT_DOMAINS_TRUST_PROXY_HEADERS": "true",
        "TENANT_DOMAINS_TRUSTED_PROXY_IPS": "127.0.0.1",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    monkeypatch.setattr(security, "settings", SimpleNamespace(
        JWT_SECRET_KEY="branding-isolated-test-secret-key", JWT_ALGORITHM="HS256", JWT_EXPIRE_MINUTES=60))
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Tenant.__table__, TenantProfile.__table__, TenantDomain.__table__,
        AdminUser.__table__, TenantMembership.__table__, Role.__table__, RbacModule.__table__,
        RbacPermission.__table__, RolePermission.__table__, UserPermission.__table__])
    with engine.begin() as connection:
        # SQLite ignores PostgreSQL partial-index predicates; these three indexes
        # would otherwise prevent unrelated nonlegacy tenants/defaults in fixtures.
        for name in ("uq_tenants_single_legacy", "uq_tenant_domains_primary_active", "uq_tenant_memberships_default_active_user"):
            connection.exec_driver_sql(f"DROP INDEX {name}")
        connection.exec_driver_sql("CREATE TABLE site_config (id VARCHAR PRIMARY KEY, content TEXT NOT NULL, updated_at TIMESTAMP)")
        connection.execute(text("INSERT INTO site_config VALUES ('default', :content, CURRENT_TIMESTAMP)"),
            {"content": json.dumps({"brand": {"name": "Legacy Shop", "faviconUrl": "/uploads/legacy.png"}})})
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    for suffix, tenant_id in (("a", "tenant-a"), ("b", "tenant-b"), ("legacy", LEGACY)):
        db.add(Tenant(id=tenant_id, slug=suffix, name=f"Shop {suffix}", status="active", is_legacy=suffix == "legacy"))
        db.add(TenantProfile(tenant_id=tenant_id, trade_name=f"Shop {suffix}", logo_url=f"/uploads/{suffix}-logo.png",
            metadata_json=json.dumps({"unrelated_setting": "preserve-me"})))
        db.add(TenantDomain(id=f"domain-{suffix}", tenant_id=tenant_id, hostname=f"{suffix}.example.com", kind="custom",
            status="active", verification_token_hash="a" * 64))
        db.add(AdminUser(id=f"admin-{suffix}", email=f"{suffix}@example.com", name=suffix,
            password_hash="unused", active=True, force_password_change=False))
        db.add(TenantMembership(id=f"membership-{suffix}", tenant_id=tenant_id, user_id=f"admin-{suffix}",
            role="owner", status="active"))
    db.commit()
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db

    @app.exception_handler(DomainError)
    def domain_error(request, exc):
        return JSONResponse(status_code=exc.http_status, content={"error": exc.code})

    def headers(suffix="a", **claims):
        tenant_id = LEGACY if suffix == "legacy" else f"tenant-{suffix}"
        token = security.create_access_token(f"admin-{suffix}", extra={
            "tenant_id": tenant_id, "membership_id": f"membership-{suffix}", **claims})
        return {"Authorization": f"Bearer {token}", "host": "app.telz.com.br"}

    with TestClient(app) as client:
        yield SimpleNamespace(client=client, db=db, headers=headers, monkeypatch=monkeypatch)
    db.close()
    engine.dispose()
    get_settings.cache_clear()


def save(branding, suffix, name=None):
    payload = {"brand": {"name": name or f"Company {suffix}", "faviconUrl": f"/uploads/{suffix}-favicon.png"}}
    response = branding.client.put("/api/admin/site-config", headers=branding.headers(suffix), json=payload)
    assert response.status_code == 200, response.text
    return payload


def test_config_favicon_and_manifest_keep_two_tenants_and_manager_separate(branding):
    for suffix in ("a", "b"):
        payload = save(branding, suffix)
        config = branding.client.get("/api/site-config", headers={"host": f"{suffix}.example.com"})
        assert config.status_code == 200
        assert config.json()["data"] == payload
        favicon = branding.client.get(READ_PATHS[1], headers={"host": f"{suffix}.example.com"}, follow_redirects=False)
        assert favicon.status_code == 307
        assert favicon.headers["location"].startswith(f"/uploads/{suffix}-favicon.png?v=")
        manifest = branding.client.get(READ_PATHS[2], headers={"host": f"{suffix}.example.com"})
        assert manifest.status_code == 200
        assert manifest.json()["name"] == f"Company {suffix}"
        assert "no-store" in manifest.headers["cache-control"]
    for host in ("app.telz.com.br", "manager.example.com"):
        config = branding.client.get(READ_PATHS[0], headers={"host": host})
        assert config.status_code == 200
        assert "Company" not in config.text and "legacy.png" not in config.text
        favicon = branding.client.get(READ_PATHS[1], headers={"host": host}, follow_redirects=False)
        assert favicon.status_code == 307
        assert "telz" in favicon.headers["location"]
        assert "no-store" in favicon.headers["cache-control"]
        manifest = branding.client.get(READ_PATHS[2], headers={"host": host})
        assert manifest.status_code == 200
        assert "Telz" in manifest.json()["name"]


@pytest.mark.parametrize("path", READ_PATHS)
@pytest.mark.parametrize("enabled", [False, True])
def test_manager_does_not_query_tenant_or_legacy_settings(branding, monkeypatch, path, enabled):
    monkeypatch.setenv("TENANT_DOMAINS_ENABLED", str(enabled).lower())
    monkeypatch.setenv("MULTI_TENANT_AUTH_ENABLED", str(enabled).lower())
    get_settings.cache_clear()
    statements = []
    def capture(_connection, _cursor, statement, parameters, _context, _many):
        statements.append((statement, parameters))
    engine = branding.db.get_bind()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = branding.client.get(path, headers={"host": "app.telz.com.br"}, follow_redirects=False)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code in (200, 307)
    assert statements, "Manager branding must read its persisted configuration"
    for statement, parameters in statements:
        assert "site_config" in statement
        assert "platform:branding" in str(parameters)
        assert "tenant:" not in str(parameters)
        assert "default" not in str(parameters)


@pytest.mark.parametrize("path", READ_PATHS)
def test_unknown_or_inactive_store_fails_closed(branding, path):
    assert branding.client.get(path, headers={"host": "unknown.example.com"}, follow_redirects=False).status_code == 404
    branding.db.query(Tenant).filter_by(id="tenant-a").one().status = "suspended"
    branding.db.commit()
    assert branding.client.get(path, headers={"host": "a.example.com"}, follow_redirects=False).status_code == 404


def test_untrusted_forwarded_host_cannot_switch_branding(branding):
    save(branding, "a")
    save(branding, "b")
    response = branding.client.get(READ_PATHS[1], headers={"host": "a.example.com", "x-forwarded-host": "b.example.com"},
        follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"].startswith("/uploads/a-favicon.png?v=")
    response = branding.client.get(READ_PATHS[1], headers={"host": "unknown.example.com", "x-forwarded-host": "app.telz.com.br"},
        follow_redirects=False)
    assert response.status_code == 404


def test_put_uses_membership_and_preserves_other_tenant_and_legacy_settings(branding):
    save(branding, "b")
    save(branding, "a")
    assert branding.client.get(READ_PATHS[0], headers={"host": "b.example.com"}).json()["data"]["brand"]["name"] == "Company b"
    legacy = json.loads(branding.db.execute(text("SELECT content FROM site_config WHERE id = 'default'")).scalar_one())
    assert legacy["brand"]["name"] == "Legacy Shop"
    profile = branding.db.query(TenantProfile).filter_by(tenant_id="tenant-a").one()
    assert json.loads(profile.metadata_json)["unrelated_setting"] == "preserve-me"
    assert branding.client.put("/api/admin/site-config", json={"brand": {"name": "Unauthorized"}}).status_code == 401
    headers = {**branding.headers(), "X-Tenant-ID": "tenant-b"}
    assert branding.client.put("/api/admin/site-config", headers=headers, json={"brand": {"name": "Cross tenant"}}).status_code == 403
    headers = {**branding.headers(), "host": "b.example.com"}
    assert branding.client.put("/api/admin/site-config", headers=headers, json={"brand": {"name": "Host mismatch"}}).status_code == 403
    headers = branding.headers(tenant_id="tenant-b", membership_id="membership-b")
    assert branding.client.put("/api/admin/site-config", headers=headers, json={"brand": {"name": "Forged selection"}}).status_code == 403
    branding.db.query(TenantMembership).filter_by(id="membership-a").one().status = "revoked"
    branding.db.commit()
    assert branding.client.put("/api/admin/site-config", headers=branding.headers(), json={"brand": {"name": "Revoked"}}).status_code == 403


def test_legacy_fallback_does_not_leak_into_other_registered_tenants(branding):
    legacy = branding.client.get(READ_PATHS[0], headers={"host": "legacy.example.com"})
    assert legacy.status_code == 200
    assert legacy.json()["data"]["brand"]["name"] == "Legacy Shop"
    other = branding.client.get(READ_PATHS[0], headers={"host": "a.example.com"})
    assert other.status_code == 200
    assert "Legacy Shop" not in other.text
    assert "legacy.png" not in other.text
    favicon = branding.client.get(READ_PATHS[1], headers={"host": "a.example.com"}, follow_redirects=False)
    assert favicon.status_code == 307
    assert favicon.headers["location"].startswith("/icons/store-default.svg?v=")
    save(branding, "legacy", name="Legacy New")
    updated = branding.client.get(READ_PATHS[0], headers={"host": "legacy.example.com"})
    assert updated.json()["data"]["brand"]["name"] == "Legacy New"
    branding.monkeypatch.setenv("TENANT_DOMAINS_ENABLED", "false")
    branding.monkeypatch.setenv("MULTI_TENANT_AUTH_ENABLED", "false")
    get_settings.cache_clear()
    compatibility = branding.client.get(READ_PATHS[0], headers={"host": "testserver"})
    assert compatibility.status_code == 200
    assert compatibility.json()["data"]["brand"]["name"] == "Legacy Shop"
