from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.services.platform_audit_service import _safe
from backend.services.platform_master_service import _admin_public, _domain_public, _support_public
from backend.services.tenant_entitlement_service import TenantAccessDenied, TenantEntitlementService
from backend.core.tenant_context import TenantContext, TenantSource
from backend.core.tenant_entitlements import require_operational_entitlement


class FakeQuery:
    def __init__(self, row):
        self.row = row

    def join(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.row


class EntitlementDB:
    def __init__(self, *, tenant, license_row, tenant_module):
        self.tenant = tenant
        self.license_row = license_row
        self.tenant_module = tenant_module

    def query(self, *models):
        from backend.models.platform_saas import SaaSModule, TenantLicense, TenantModule
        from backend.models.tenant import Tenant

        model = models[0]
        if model is Tenant:
            return FakeQuery(self.tenant)
        if model is TenantLicense:
            return FakeQuery(self.license_row)
        if models == (TenantModule, SaaSModule):
            catalog = SimpleNamespace(dependencies_json="[]")
            return FakeQuery((self.tenant_module, catalog) if self.tenant_module else None)
        if model is TenantModule:
            return FakeQuery(self.tenant_module)
        raise AssertionError(f"unexpected model {model}")


def _license(tenant_id: str):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        tenant_id=tenant_id, status="active", trial_ends_at=None,
        expires_at=now + timedelta(days=30), grace_period_ends_at=None,
    )


def test_tenant_a_entitlement_never_grants_tenant_b_without_its_own_module():
    tenant_a = SimpleNamespace(id="tenant-a", status="active", deleted_at=None)
    module_a = SimpleNamespace(tenant_id="tenant-a", enabled=True, ends_at=None, limit_value=None)
    allowed = TenantEntitlementService(EntitlementDB(
        tenant=tenant_a, license_row=_license("tenant-a"), tenant_module=module_a,
    )).require_module("tenant-a", "orders", write=True)
    assert allowed.tenant_id == "tenant-a"

    tenant_b = SimpleNamespace(id="tenant-b", status="active", deleted_at=None)
    with pytest.raises(TenantAccessDenied, match="nao contratado"):
        TenantEntitlementService(EntitlementDB(
            tenant=tenant_b, license_row=_license("tenant-b"), tenant_module=None,
        )).require_module("tenant-b", "orders", write=True)


def test_expired_license_blocks_write_server_side():
    expired = _license("tenant-a")
    expired.status = "expired"
    service = TenantEntitlementService(EntitlementDB(
        tenant=SimpleNamespace(id="tenant-a", status="active", deleted_at=None),
        license_row=expired, tenant_module=None,
    ))
    with pytest.raises(TenantAccessDenied, match="nao permite"):
        service.require_tenant_access("tenant-a", write=True)


def test_public_serializers_never_expose_hashes():
    admin = SimpleNamespace(
        id="u", email="u@example.com", name="User", active=True, phone=None,
        role_id="role", last_login_at=None, created_at=None, updated_at=None,
        force_password_change=False,
        password_hash="must-not-leak",
    )
    assert "password_hash" not in _admin_public(admin)

    def table(*names):
        return SimpleNamespace(columns=[SimpleNamespace(name=name) for name in names])

    domain = SimpleNamespace(
        __table__=table("id", "hostname", "verification_token_hash"),
        id="d", hostname="store.example.com", verification_token_hash="must-not-leak",
    )
    support = SimpleNamespace(
        __table__=table("id", "status", "token_hash"),
        id="s", status="active", token_hash="must-not-leak",
    )
    assert "verification_token_hash" not in _domain_public(domain)
    assert "token_hash" not in _support_public(support)


def test_audit_redacts_nested_secret_patterns():
    safe = _safe({
        "owner": {"password": "x", "client_secret": "y"},
        "headers": {"authorization": "Bearer z", "cookie": "session=x"},
        "runtime_token_hash": "hash",
    })
    assert safe["owner"]["password"] == "[REDACTED]"
    assert safe["owner"]["client_secret"] == "[REDACTED]"
    assert safe["headers"]["authorization"] == "[REDACTED]"
    assert safe["headers"]["cookie"] == "[REDACTED]"
    assert safe["runtime_token_hash"] == "[REDACTED]"

    opaque = _safe({
        "config_json": '{"unrecognized_provider_credential":"raw-secret"}',
        "default_config_json": '{"public":"value"}',
    })
    assert opaque["config_json"] == "[REDACTED]"
    assert opaque["default_config_json"] == "[REDACTED]"


def test_entitlement_flag_off_preserves_legacy_without_resolving_context(monkeypatch):
    monkeypatch.setattr(
        "backend.core.tenant_entitlements.get_settings",
        lambda: SimpleNamespace(TENANT_ENTITLEMENT_ENFORCEMENT_ENABLED=False),
    )
    monkeypatch.setattr(
        "backend.core.tenant_entitlements.resolve_panel_tenant_context",
        lambda *_args: (_ for _ in ()).throw(AssertionError("context should not resolve")),
    )
    dependency = require_operational_entitlement("orders.write", write=True)
    assert dependency(SimpleNamespace(), object(), SimpleNamespace(id="admin")) is None


def test_entitlement_flag_on_keeps_tenant_a_and_b_isolated(monkeypatch):
    monkeypatch.setattr(
        "backend.core.tenant_entitlements.get_settings",
        lambda: SimpleNamespace(TENANT_ENTITLEMENT_ENFORCEMENT_ENABLED=True),
    )
    current = {"tenant_id": "tenant-a"}
    monkeypatch.setattr(
        "backend.core.tenant_entitlements.resolve_panel_tenant_context",
        lambda *_args: TenantContext(
            tenant_id=current["tenant_id"], source=TenantSource.PANEL,
            actor_id="admin", membership_id=f"membership-{current['tenant_id']}",
        ),
    )

    class Policy:
        def require_module(self, tenant_id, module_key, *, write):
            if tenant_id != "tenant-a":
                raise TenantAccessDenied("Tenant B sem modulo.", code="TenantModuleDenied")
            return SimpleNamespace(tenant_id=tenant_id, module_key=module_key, write=write)

    monkeypatch.setattr(
        "backend.core.tenant_entitlements.TenantEntitlementService",
        lambda _db: Policy(),
    )
    dependency = require_operational_entitlement("orders.write", write=True)
    allowed = dependency(SimpleNamespace(), object(), SimpleNamespace(id="admin"))
    assert allowed.tenant_id == "tenant-a"
    current["tenant_id"] = "tenant-b"
    with pytest.raises(TenantAccessDenied, match="Tenant B"):
        dependency(SimpleNamespace(), object(), SimpleNamespace(id="admin"))
