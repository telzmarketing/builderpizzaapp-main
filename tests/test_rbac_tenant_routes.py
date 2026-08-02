import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.models.admin import AdminUser
from backend.models.membership import TenantMembership
from backend.models.rbac import Role
from backend.routes import admin_users, rbac
from backend.schemas.rbac import RoleUpdate
from backend.services.tenant_auth_service import (
    TenantAuthSelection,
    TenantAuthService,
    TenantMembershipDenied,
)


ROOT = Path(__file__).parents[1]
ROUTE = ROOT / "backend/routes/rbac.py"
ADMIN_USERS_ROUTE = ROOT / "backend/routes/admin_users.py"
TENANT_OWNED_MODELS = {"Role", "RolePermission", "UserPermission", "AdminAuditLog"}


def test_every_tenant_owned_rbac_constructor_sets_tenant_id():
    tree = ast.parse(ROUTE.read_text(encoding="utf-8"))
    constructors = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in TENANT_OWNED_MODELS
    ]

    assert constructors
    assert {node.func.id for node in constructors} == TENANT_OWNED_MODELS
    for constructor in constructors:
        assert any(keyword.arg == "tenant_id" for keyword in constructor.keywords), (
            f"{constructor.func.id} sem tenant_id na linha {constructor.lineno}"
        )


def test_rbac_tenant_comes_from_trusted_panel_context_with_explicit_legacy_mode():
    route = ROUTE.read_text(encoding="utf-8")

    assert "resolve_panel_tenant_context(request, db, user)" in route
    assert 'LEGACY_TENANT_ID = "tenant-legacy-default"' in route
    assert "_TenantScope(tenant_id=LEGACY_TENANT_ID, enforced=False)" in route
    assert "_TenantScope(tenant_id=context.tenant_id, enforced=True)" in route


def test_admin_user_routes_scope_roles_memberships_and_audit_to_tenant():
    route = ADMIN_USERS_ROUTE.read_text(encoding="utf-8")

    assert "resolve_panel_tenant_context(request, db, user)" in route
    assert "Role.tenant_id == scope.tenant_id" in route
    assert "TenantMembership.tenant_id == scope.tenant_id" in route
    assert "tenant_id=scope.tenant_id" in route
    assert "PlatformRole" not in route
    assert "PlatformPermission" not in route


def _selection(tenant_id: str) -> TenantAuthSelection:
    return TenantAuthSelection(
        tenant_id=tenant_id,
        membership_id=f"membership-{tenant_id}",
        tenant_role="owner",
        tenant_name=tenant_id,
        tenant_slug=tenant_id,
        is_default=False,
    )


def test_global_role_id_fails_closed_for_multiple_active_memberships(monkeypatch):
    service = TenantAuthService(SimpleNamespace())
    monkeypatch.setattr(
        service,
        "list_active",
        lambda _user_id: [_selection("tenant-a"), _selection("tenant-b")],
    )

    assert service.login_selection("user") is None
    with pytest.raises(TenantMembershipDenied, match="multiplas memberships"):
        service.require_selection("user", "tenant-a")


class _MemoryQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    @staticmethod
    def _resource(row, table_name: str):
        if not isinstance(row, tuple):
            return row
        if table_name == "admin_users":
            return row[0]
        if table_name == "tenant_memberships":
            return row[1]
        return row[0]

    def filter(self, *criteria):
        rows = self.rows
        for criterion in criteria:
            table_name = criterion.left.table.name
            column_name = criterion.left.name
            expected = criterion.right.value
            operator = criterion.operator.__name__

            def matches(row):
                actual = getattr(self._resource(row, table_name), column_name)
                if operator == "eq":
                    return actual == expected
                if operator == "ne":
                    return actual != expected
                raise AssertionError(f"operador inesperado: {operator}")

            rows = [row for row in rows if matches(row)]
        return _MemoryQuery(rows)

    def join(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows


class _MemoryDb:
    def __init__(self):
        self.roles = [
            SimpleNamespace(id="master-a", tenant_id="tenant-a", name="Master"),
            SimpleNamespace(id="role-b", tenant_id="tenant-b", name="Master"),
        ]
        self.users = [
            SimpleNamespace(id="user-a"),
            SimpleNamespace(id="user-b"),
        ]
        self.memberships = [
            SimpleNamespace(
                id="membership-a", user_id="user-a", tenant_id="tenant-a",
                status="active", role="owner",
            ),
            SimpleNamespace(
                id="membership-b", user_id="user-b", tenant_id="tenant-b",
                status="active", role="owner",
            ),
        ]

    def query(self, *models):
        if len(models) == 1 and models[0] is Role:
            return _MemoryQuery(self.roles)
        if len(models) == 1 and (
            models[0] is TenantMembership or models[0] is TenantMembership.id
        ):
            return _MemoryQuery(self.memberships)
        if len(models) == 2 and models[0] is AdminUser and models[1] is TenantMembership:
            return _MemoryQuery(list(zip(self.users, self.memberships)))
        raise AssertionError(f"consulta inesperada: {models}")


def test_tenant_a_cannot_read_or_update_tenant_b_role(monkeypatch):
    db = _MemoryDb()
    scope = rbac._TenantScope(tenant_id="tenant-a", enforced=True)
    monkeypatch.setattr(rbac, "_tenant_scope", lambda *_args: scope)
    actor = SimpleNamespace(id="user-a", role_id="master-a")
    request = SimpleNamespace()

    with pytest.raises(HTTPException) as read_error:
        rbac.get_role_permissions("role-b", request, db, actor)
    assert read_error.value.status_code == 404

    with pytest.raises(HTTPException) as update_error:
        rbac.update_role(
            "role-b", RoleUpdate(description="cross-tenant"), request, db, actor
        )
    assert update_error.value.status_code == 404


def test_tenant_a_admin_user_crud_cannot_target_tenant_b(monkeypatch):
    db = _MemoryDb()
    scope = admin_users._TenantScope(tenant_id="tenant-a", enforced=True)
    rows = admin_users._tenant_user_rows(db, scope)
    assert [user.id for user, _membership in rows] == ["user-a"]

    monkeypatch.setattr(admin_users, "_tenant_scope", lambda *_args: scope)
    actor = SimpleNamespace(id="user-a", role_id="master-a")
    with pytest.raises(HTTPException) as update_error:
        admin_users.update_admin_user(
            "user-b",
            admin_users.AdminUserUpdate(name="cross-tenant"),
            SimpleNamespace(),
            db,
            actor,
        )
    assert update_error.value.status_code == 404


def test_active_owner_membership_can_manage_tenant_but_global_role_cannot():
    db = _MemoryDb()
    scope = rbac._TenantScope(tenant_id="tenant-a", enforced=True)
    owner = SimpleNamespace(id="user-a", role_id="master-a")
    platform_only = SimpleNamespace(id="platform-user", role_id="master-a")

    assert rbac._is_master(owner, db, scope)
    assert admin_users._is_master(
        owner,
        db,
        admin_users._TenantScope(tenant_id="tenant-a", enforced=True),
    )
    assert not rbac._is_master(platform_only, db, scope)
    assert not admin_users._is_master(
        platform_only,
        db,
        admin_users._TenantScope(tenant_id="tenant-a", enforced=True),
    )


def test_global_identity_mutation_rejects_any_foreign_non_revoked_membership():
    db = _MemoryDb()
    db.memberships.append(SimpleNamespace(
        id="membership-a-foreign",
        user_id="user-a",
        tenant_id="tenant-b",
        status="suspended",
        role="viewer",
    ))
    scope = admin_users._TenantScope(tenant_id="tenant-a", enforced=True)

    with pytest.raises(HTTPException) as error:
        admin_users._require_tenant_owned_identity(db, "user-a", scope)
    assert error.value.status_code == 409

    db.memberships[-1].status = "revoked"
    admin_users._require_tenant_owned_identity(db, "user-a", scope)


def test_admin_user_password_schemas_enforce_bcrypt_byte_limit():
    oversized_unicode = "é" * 40
    with pytest.raises(ValidationError):
        admin_users.AdminUserCreate(
            name="Owner",
            email="owner@example.com",
            password=oversized_unicode,
        )
    with pytest.raises(ValidationError):
        admin_users.AdminUserUpdate(password=oversized_unicode)
    with pytest.raises(ValidationError):
        admin_users.ResetPasswordIn(new_password=oversized_unicode)


def test_owner_membership_cannot_be_demoted_or_deactivated_directly():
    membership = SimpleNamespace(role="owner")
    with pytest.raises(HTTPException) as role_error:
        admin_users._protect_owner_membership(membership, role_change=True)
    assert role_error.value.status_code == 409
    with pytest.raises(HTTPException) as status_error:
        admin_users._protect_owner_membership(membership, status_change=True)
    assert status_error.value.status_code == 409


def test_admin_user_password_mutations_increment_auth_version():
    route = ADMIN_USERS_ROUTE.read_text(encoding="utf-8")
    increment = 'user.auth_version = int(getattr(user, "auth_version", 0) or 0) + 1'
    assert route.count(increment) == 2
