from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from backend.core.platform_authorization import require_platform_permission
from backend.services.tenant_credential_service import TenantCredentialConfigurationError, TenantCredentialService, TenantCredentialsDisabled

class Query:
    def __init__(self, rows): self.rows = rows
    def filter(self, *_args): return self
    def limit(self, _value): return self
    def all(self): return self.rows
class DB:
    def __init__(self, rows): self.rows = rows
    def query(self, _model): return Query(self.rows)

def test_tenant_credentials_disabled_by_default(monkeypatch):
    monkeypatch.setattr("backend.services.tenant_credential_service.get_settings", lambda: SimpleNamespace(TENANT_CREDENTIALS_ENABLED=False))
    with pytest.raises(TenantCredentialsDisabled): TenantCredentialService(DB([])).payment_gateway("tenant-a")

def test_tenant_credentials_require_one_row(monkeypatch):
    monkeypatch.setattr("backend.services.tenant_credential_service.get_settings", lambda: SimpleNamespace(TENANT_CREDENTIALS_ENABLED=True))
    with pytest.raises(TenantCredentialConfigurationError): TenantCredentialService(DB([])).payment_gateway("tenant-a")
    expected = object()
    assert TenantCredentialService(DB([expected])).payment_gateway("tenant-a") is expected

def test_platform_dependency_does_not_infer_master(monkeypatch):
    monkeypatch.setattr("backend.core.platform_authorization.get_settings", lambda: SimpleNamespace(PLATFORM_RBAC_ENABLED=True))
    monkeypatch.setattr("backend.core.platform_authorization.has_platform_permission", lambda *_args: False)
    with pytest.raises(HTTPException) as exc: require_platform_permission("tenants.manage")(SimpleNamespace(id="u", role_id=None), object())
    assert exc.value.status_code == 403

def test_platform_dependency_hidden_when_off(monkeypatch):
    monkeypatch.setattr("backend.core.platform_authorization.get_settings", lambda: SimpleNamespace(PLATFORM_RBAC_ENABLED=False))
    with pytest.raises(HTTPException) as exc: require_platform_permission("tenants.manage")(SimpleNamespace(id="u"), object())
    assert exc.value.status_code == 404

def test_platform_dependency_rejects_support_token(monkeypatch):
    monkeypatch.setattr("backend.core.platform_authorization.get_settings", lambda: SimpleNamespace(PLATFORM_RBAC_ENABLED=True))
    monkeypatch.setattr("backend.core.platform_authorization.decode_access_token", lambda _token: {"token_kind": "support"})
    monkeypatch.setattr("backend.core.platform_authorization.has_platform_permission", lambda *_args: True)
    with pytest.raises(HTTPException) as exc:
        require_platform_permission("tenants.view")(
            SimpleNamespace(id="u"), object(), "Bearer support-token"
        )
    assert exc.value.status_code == 403
