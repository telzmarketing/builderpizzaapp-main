from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app as registered_app  # noqa: F401 - register related ORM metadata
from backend.core import security, tenant_auth, tenant_runtime
from backend.core.exceptions import DomainError
from backend.database import Base, get_db
from backend.models.admin import AdminUser
from backend.models.membership import TenantMembership
from backend.models.platform_audit import PlatformAuditLog
from backend.models.platform_operations import PlatformWorkerHeartbeat
from backend.models.rbac import Role, RbacModule, RbacPermission, RolePermission, UserPermission
from backend.models.tenant import Tenant
from backend.models.tenant_domain import TenantDomain
from backend.models.tenant_domain_ssl import TenantDomainCertificateJob
from backend.routes.company_domains import router
from backend.services import tenant_domain_self_service, tenant_domain_ssl_service


@pytest.fixture
def company(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Tenant.__table__, AdminUser.__table__, TenantMembership.__table__,
        Role.__table__, RbacModule.__table__, RbacPermission.__table__, RolePermission.__table__, UserPermission.__table__,
        TenantDomain.__table__, TenantDomainCertificateJob.__table__, PlatformAuditLog.__table__, PlatformWorkerHeartbeat.__table__])
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX uq_tenant_domains_primary_active")
        connection.exec_driver_sql("DROP INDEX uq_tenants_single_legacy")
        connection.exec_driver_sql("DROP INDEX uq_tenant_memberships_default_active_user")
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    now = tenant_domain_ssl_service.utcnow()
    for suffix in ("a", "b"):
        db.add(Tenant(id=f"tenant-{suffix}", slug=f"tenant-{suffix}", name=suffix, status="active"))
        db.add(AdminUser(id=f"admin-{suffix}", name=suffix, email=f"{suffix}@example.com", password_hash="unused", active=True,
            role_id=f"role-{suffix}", force_password_change=False))
        db.add(Role(id=f"role-{suffix}", tenant_id=f"tenant-{suffix}", name="Operador"))
        db.add(TenantMembership(id=f"membership-{suffix}", tenant_id=f"tenant-{suffix}", user_id=f"admin-{suffix}", role="operator", status="active"))
        db.add(TenantDomain(id=f"domain-{suffix}", tenant_id=f"tenant-{suffix}", hostname=f"{suffix}.example.com",
            kind="custom", status="verified", verified_at=now, verification_token_hash="a" * 64, ssl_status="pending"))
    db.add(RbacModule(id="module-config", key="configuracoes", name="Configuracoes", is_active=True))
    for permission in ("view", "edit"):
        db.add(RbacPermission(id=permission, key=permission, name=permission))
        for suffix in ("a", "b"):
            db.add(RolePermission(id=f"{suffix}-{permission}", tenant_id=f"tenant-{suffix}", role_id=f"role-{suffix}",
                module_id="module-config", permission_id=permission, allowed=True))
    db.commit()
    settings = SimpleNamespace(MULTI_TENANT_AUTH_ENABLED=True, TENANT_DOMAIN_SSL_MODE="manual", TENANT_DOMAIN_SSL_ENABLED=True,
        TENANT_DOMAIN_SSL_PUBLIC_IPS="8.8.8.8", TENANT_DOMAINS_PLATFORM_HOSTNAMES="app.example.com",
        TENANT_DOMAIN_SSL_HEARTBEAT_SECONDS=300, TENANT_DOMAIN_SSL_LEASE_SECONDS=900, TENANT_DOMAIN_SSL_COOLDOWN_SECONDS=3600)
    for module in (tenant_auth, tenant_runtime, tenant_domain_ssl_service, tenant_domain_self_service):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "settings", SimpleNamespace(JWT_EXPIRE_MINUTES=60, JWT_SECRET_KEY="self-service-test-key", JWT_ALGORITHM="HS256"))
    monkeypatch.setattr(tenant_domain_ssl_service, "resolve_public_addresses", lambda host, **kwargs: {"8.8.8.8"})
    def absent_certificate(host, **kwargs):
        raise tenant_domain_ssl_service.CertificateError("TLS_INVALID")
    monkeypatch.setattr(tenant_domain_ssl_service, "probe_certificate", absent_certificate)
    tenant_domain_ssl_service.TenantDomainSSLService(db).heartbeat()
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    @app.exception_handler(DomainError)
    def domain_error(request, exc):
        return JSONResponse(status_code=exc.http_status, content={"error": exc.code})
    client = TestClient(app)
    def headers(suffix="a", **claims):
        token = security.create_access_token(f"admin-{suffix}", extra={"tenant_id": f"tenant-{suffix}",
            "membership_id": f"membership-{suffix}", **claims})
        return {"Authorization": f"Bearer {token}"}
    yield SimpleNamespace(db=db, client=client, headers=headers, settings=settings)
    client.close()
    db.close()
    engine.dispose()


def test_real_jwt_membership_and_rbac_limit_list_to_current_tenant(company):
    response = company.client.get("/api/admin/company/domains", headers=company.headers())
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]] == ["domain-a"]
    assert "verification_token_hash" not in response.text
    assert company.client.get("/api/admin/company/domains", headers=company.headers("b")).json()["data"][0]["id"] == "domain-b"


@pytest.mark.parametrize("suffix", ["verify", "activate", "primary", "certificate"])
def test_every_mutation_rejects_other_tenants_domain_before_delegation(company, suffix):
    kwargs = {"headers": company.headers()}
    if suffix == "certificate":
        kwargs["headers"]["Idempotency-Key"] = str(uuid4())
        kwargs["json"] = {"email": "admin@example.com", "accept_terms": True}
    assert company.client.post(f"/api/admin/company/domains/domain-b/{suffix}", **kwargs).status_code == 404
    assert company.db.query(TenantDomainCertificateJob).count() == 0


def test_certificate_read_and_replayed_key_cannot_cross_tenant(company):
    headers = {**company.headers(), "Idempotency-Key": str(uuid4())}
    response = company.client.post("/api/admin/company/domains/domain-a/certificate", headers=headers,
        json={"email": "admin@example.com", "accept_terms": True})
    assert response.status_code == 202
    assert response.json()["data"]["job"]["status"] == "queued"
    assert company.client.post("/api/admin/company/domains/domain-a/certificate", headers={**headers, **company.headers("b")},
        json={"email": "admin@example.com", "accept_terms": True}).status_code == 404
    assert company.client.get("/api/admin/company/domains/domain-a/certificate", headers=company.headers("b")).status_code == 404
    assert company.db.query(TenantDomainCertificateJob).count() == 1


def test_rbac_is_enforced_with_real_role_and_negative_user_override(company):
    company.db.query(RolePermission).filter(RolePermission.id == "a-edit").one().allowed = False
    company.db.commit()
    assert company.client.get("/api/admin/company/domains", headers=company.headers()).status_code == 200
    assert company.client.post("/api/admin/company/domains/domain-a/verify", headers=company.headers()).status_code == 403
    company.db.add(UserPermission(id="deny-view", tenant_id="tenant-a", user_id="admin-a", module_id="module-config",
        permission_id="view", allowed=False, overrides_role=True))
    company.db.commit()
    assert company.client.get("/api/admin/company/domains", headers=company.headers()).status_code == 403


def test_missing_membership_support_legacy_and_revoked_membership_fail_closed(company):
    path = "/api/admin/company/domains"
    assert company.client.get(path).status_code == 401
    assert company.client.get(path, headers=company.headers(membership_id=None)).status_code == 409
    assert company.client.get(path, headers=company.headers(token_kind="support", support_session_id="support-1")).status_code == 403
    company.settings.MULTI_TENANT_AUTH_ENABLED = False
    assert company.client.get(path, headers=company.headers()).status_code == 404
    company.settings.MULTI_TENANT_AUTH_ENABLED = True
    company.db.query(TenantMembership).filter(TenantMembership.id == "membership-a").one().status = "revoked"
    company.db.commit()
    assert company.client.get(path, headers=company.headers()).status_code == 403


def test_create_ignores_no_tenant_input_and_returns_challenge_only_once(company):
    body = {"hostname": "new.example.com", "kind": "custom"}
    assert company.client.post("/api/admin/company/domains", headers=company.headers(), json={**body, "tenant_id": "tenant-b"}).status_code == 422
    created = company.client.post("/api/admin/company/domains", headers=company.headers(), json=body)
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["domain"]["tenant_id"] == "tenant-a"
    assert data["verification"]["record_value"]
    listing = company.client.get("/api/admin/company/domains", headers=company.headers())
    assert data["verification"]["record_value"] not in listing.text
    assert company.db.query(PlatformAuditLog).filter(PlatformAuditLog.action == "domain_created").one().actor_user_id == "admin-a"


def test_authorized_actor_must_match_panel_membership_exactly():
    from fastapi import HTTPException
    from backend.core.rbac_authorization import AuthorizedTenantActor
    from backend.core.tenant_context import TenantContext, TenantSource
    from backend.routes.company_domains import company_domain_actor
    context = TenantContext("tenant-a", TenantSource.PANEL, actor_id="admin-a", membership_id="membership-a")
    mismatch = TenantContext("tenant-a", TenantSource.PANEL, actor_id="admin-a", membership_id="different")
    actor = AuthorizedTenantActor("tenant-a", "admin-a", "A", mismatch)
    with pytest.raises(HTTPException) as error:
        company_domain_actor("view")(context=context, actor=actor, admin=SimpleNamespace(id="admin-a"))
    assert error.value.status_code == 403
