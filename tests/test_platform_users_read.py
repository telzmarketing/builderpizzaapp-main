from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models.admin import AdminUser
from backend.models.membership import TenantMembership
from backend.models.platform_rbac import PlatformRole, PlatformUserRole
from backend.models.tenant import Tenant  # noqa: F401 - registers FK metadata only
from backend.schemas.platform_users import PlatformUserPageOut
from backend.services.platform_user_service import PlatformUserService


ROOT = Path(__file__).parents[1]


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            AdminUser.__table__,
            PlatformRole.__table__,
            PlatformUserRole.__table__,
            TenantMembership.__table__,
        ],
    )
    with engine.begin() as connection:
        # PostgreSQL applies this unique index only to active default rows.
        # SQLite ignores postgresql_where and would make every user_id unique.
        connection.exec_driver_sql(
            "DROP INDEX uq_tenant_memberships_default_active_user"
        )
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    roles = [
        PlatformRole(
            id="role-owner",
            key="platform_owner",
            name="Owner",
            description="Full platform access",
            is_system=True,
        ),
        PlatformRole(
            id="role-support",
            key="platform_support",
            name="Support",
            is_system=True,
        ),
    ]
    users = [
        AdminUser(
            id="user-ana",
            email="ana@example.com",
            name="Ana",
            password_hash="secret-ana",
            auth_version=7,
            active=True,
        ),
        AdminUser(
            id="user-bruno",
            email="bruno@example.com",
            name="Bruno",
            password_hash="secret-bruno",
            auth_version=9,
            active=False,
        ),
        AdminUser(
            id="tenant-only",
            email="tenant@example.com",
            name="Tenant only",
            password_hash="secret-tenant",
            active=True,
        ),
    ]
    platform_roles = [
        PlatformUserRole(
            id="link-ana-support",
            user_id="user-ana",
            role_id="role-support",
        ),
        PlatformUserRole(
            id="link-ana-owner",
            user_id="user-ana",
            role_id="role-owner",
        ),
        PlatformUserRole(
            id="link-bruno-support",
            user_id="user-bruno",
            role_id="role-support",
        ),
    ]
    memberships = [
        TenantMembership(
            id="membership-ana-active",
            tenant_id="tenant-1",
            user_id="user-ana",
            role="owner",
            status="active",
        ),
        TenantMembership(
            id="membership-ana-revoked",
            tenant_id="tenant-2",
            user_id="user-ana",
            role="viewer",
            status="revoked",
        ),
        TenantMembership(
            id="membership-bruno-suspended",
            tenant_id="tenant-2",
            user_id="user-bruno",
            role="operator",
            status="suspended",
        ),
    ]
    # SQLite keeps foreign-key enforcement disabled by default in this focused
    # unit fixture, so tenant rows are unnecessary for the membership counts.
    # Avoid creating the PostgreSQL-only partial tenant index as a plain unique
    # index under SQLite, which would make unrelated tenant inserts fail.
    session.add_all(roles + users + platform_roles + memberships)
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_list_users_returns_only_global_users_with_safe_fields(db):
    result = PlatformUserService(db).list_users(page=1, page_size=20)
    validated = PlatformUserPageOut.model_validate(result)

    assert validated.total == 2
    assert validated.pages == 1
    assert [item.id for item in validated.items] == ["user-ana", "user-bruno"]

    ana = result["items"][0]
    assert ana["status"] == "active"
    assert ana["membership_count"] == 1
    assert [role["key"] for role in ana["platform_roles"]] == [
        "platform_owner",
        "platform_support",
    ]
    assert "password_hash" not in ana
    assert "auth_version" not in ana
    assert "role_id" not in ana


def test_list_users_supports_search_status_role_and_pagination(db):
    service = PlatformUserService(db)

    searched = service.list_users(page=1, page_size=20, q="BRUNO@EXAMPLE")
    assert [item["id"] for item in searched["items"]] == ["user-bruno"]

    inactive = service.list_users(page=1, page_size=20, status="inactive")
    assert [item["id"] for item in inactive["items"]] == ["user-bruno"]

    owner = service.list_users(page=1, page_size=20, role="PLATFORM_OWNER")
    assert [item["id"] for item in owner["items"]] == ["user-ana"]

    second_page = service.list_users(page=2, page_size=1)
    assert second_page["total"] == 2
    assert second_page["pages"] == 2
    assert [item["id"] for item in second_page["items"]] == ["user-bruno"]


def test_platform_users_route_is_read_only_protected_and_registered():
    route = (ROOT / "backend/routes/platform_users.py").read_text(encoding="utf-8")
    main = (ROOT / "backend/main.py").read_text(encoding="utf-8")

    assert 'prefix="/admin/platform/users"' in route
    assert '@router.get("", response_model=ApiEnvelope[PlatformUserPageOut])' in route
    assert 'require_platform_permission("platform_users.view")' in route
    assert "@router.post" not in route
    assert "@router.put" not in route
    assert "@router.patch" not in route
    assert "@router.delete" not in route
    assert "from backend.routes import platform_users as platform_users_routes" in main
    assert 'app.include_router(platform_users_routes.router, prefix="/api")' in main
