"""Real HTTP, RBAC queries and persisted effects in an isolated SQLite DB."""
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import test_kds_stock_gate
from test_kds_stock_gate import gate
from test_production_effects_commands import effects
from backend.core import rbac_authorization
from backend.core.tenant_context import TenantContext, TenantSource
from backend.database import Base, get_db
from backend.main import app as runtime_app
from backend.models.kds_production import ProductionAttempt, ProductionEffect
from backend.models.membership import TenantMembership
from backend.models.order import Order
from backend.models.rbac import RbacModule, RbacPermission, Role, RolePermission, UserPermission
from backend.routes.admin_auth import get_current_admin
from backend.routes.production_effects import router


@pytest.fixture(autouse=True)
def shared_http_database(monkeypatch):
    # Only this test fixture changes; application engines are never accessed.
    monkeypatch.setattr(test_kds_stock_gate, "create_engine", lambda *args, **kwargs: create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    ))


@pytest.fixture
def api(effects, monkeypatch):
    Base.metadata.create_all(effects.db.get_bind(), tables=[model.__table__ for model in (
        TenantMembership, Role, RbacModule, RbacPermission, RolePermission, UserPermission,
    )])
    effects.db.add(Role(id="operator-role", tenant_id="tenant", name="Operador autorizado"))
    effects.db.add(TenantMembership(id="membership", tenant_id="tenant", user_id="cook", role="operator", status="active"))
    effects.db.add(RbacPermission(id="edit", key="edit", name="Editar"))
    for module in ("cozinha", "pedidos"):
        effects.db.add(RbacModule(id=module, key=module, name=module))
        effects.db.add(RolePermission(id=f"grant-{module}", tenant_id="tenant", role_id="operator-role",
            module_id=module, permission_id="edit", allowed=True))
    effects.db.commit()
    admin = SimpleNamespace(id="cook", name="Operador", role_id="operator-role")
    context = [TenantContext("tenant", TenantSource.PANEL, actor_id="cook", membership_id="membership")]
    monkeypatch.setattr(rbac_authorization, "resolve_panel_tenant_context", lambda *args: context[0])
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: effects.db
    app.dependency_overrides[get_current_admin] = lambda: admin
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, app=app, context=context, admin=admin, effects=effects)


def loss_body(api):
    attempt = api.effects.db.get(ProductionAttempt, "task1")
    attempt.state = attempt.unit.state = "assembling"
    attempt.started_at = datetime.now(timezone.utc)
    api.effects.db.commit()
    return {"attempt_id": "task1", "expected_version": 1, "reason": "Pizza queimada"}


def test_http_loss_and_reproduction_persist_and_replay(api):
    body = loss_body(api)
    response = api.client.post("/api/production-effects/losses", json=body, headers={"Idempotency-Key": "loss"})
    assert response.status_code == 201, response.text
    original = response.json()
    replay = api.client.post("/api/production-effects/losses", json=body, headers={"Idempotency-Key": "loss"})
    assert replay.status_code == 201 and replay.json() == original
    request = {"loss_id": original["data"]["id"], "reason": "Refazer"}
    remake = api.client.post("/api/production-effects/reproductions", json=request, headers={"Idempotency-Key": "remake"})
    assert remake.status_code == 201, remake.text
    assert remake.json()["data"]["source_effect_id"] == original["data"]["id"]
    assert api.client.post("/api/production-effects/reproductions", json=request, headers={"Idempotency-Key": "remake"}).json() == remake.json()
    assert api.effects.db.query(ProductionEffect).count() == 2


def test_http_bonification_uses_orders_permission_and_replays(api):
    api.effects.db.get(Order, "order1").status = "pending"
    api.effects.db.commit()
    body = {"order_id": "order1", "reason": "Janta", "beneficiary": "Equipe de trabalho"}
    path, headers = "/api/production-effects/bonifications", {"Idempotency-Key": "bonus"}
    response = api.client.post(path, json=body, headers=headers)
    assert response.status_code == 201, response.text
    assert response.json()["data"]["discount_amount"] == "50.00"
    assert api.client.post(path, json=body, headers=headers).json() == response.json()
    assert api.effects.db.get(Order, "order1").total == 0


@pytest.mark.parametrize("key", [None, "", " " * 3, "x" * 201])
def test_header_is_required_and_validated_before_effect(api, key):
    body = loss_body(api)
    headers = {} if key is None else {"Idempotency-Key": key}
    response = api.client.post("/api/production-effects/losses", json=body, headers=headers)
    assert response.status_code in {400, 422}
    assert api.effects.db.query(ProductionEffect).count() == 0


@pytest.mark.parametrize("module,path,body", [
    ("cozinha", "losses", {"attempt_id": "task1", "expected_version": 1, "reason": "Perda"}),
    ("cozinha", "reproductions", {"loss_id": "loss", "reason": "Refazer"}),
    ("pedidos", "bonifications", {"order_id": "order1", "reason": "Janta", "beneficiary": "Equipe"}),
])
def test_rbac_denies_each_command_without_its_permission(api, module, path, body):
    api.effects.db.get(RolePermission, f"grant-{module}").allowed = False
    api.effects.db.commit()
    response = api.client.post(f"/api/production-effects/{path}", json=body, headers={"Idempotency-Key": "denied"})
    assert response.status_code == 403
    assert api.effects.db.query(ProductionEffect).count() == 0


def test_anonymous_caller_cannot_register_effect(api):
    del api.app.dependency_overrides[get_current_admin]
    response = api.client.post("/api/production-effects/losses", json=loss_body(api), headers={"Idempotency-Key": "anonymous"})
    assert response.status_code == 401


def test_http_conflict_and_payload_cannot_spoof_tenant_or_actor(api):
    body = loss_body(api)
    path, headers = "/api/production-effects/losses", {"Idempotency-Key": "loss"}
    for field in ("tenant_id", "actor_id"):
        assert api.client.post(path, json={**body, field: "spoof"}, headers=headers).status_code == 422
    assert api.client.post(path, json=body, headers=headers).status_code == 201
    response = api.client.post(path, json={**body, "reason": "Changed"}, headers=headers)
    assert response.status_code == 409 and response.json()["error"]["code"] == "IdempotencyConflict"


def test_selected_tenant_cannot_use_another_tenants_rbac_role(api):
    api.context[0] = TenantContext("other", TenantSource.PANEL, actor_id="cook", membership_id="other-membership")
    response = api.client.post("/api/production-effects/losses", json=loss_body(api), headers={"Idempotency-Key": "other"})
    assert response.status_code == 403
    assert api.effects.db.query(ProductionEffect).count() == 0


def test_router_is_registered_on_real_application():
    paths = {route.path for route in runtime_app.routes}
    assert {"/api/production-effects/losses", "/api/production-effects/reproductions",
            "/api/production-effects/bonifications"} <= paths
