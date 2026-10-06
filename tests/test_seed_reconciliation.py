from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from backend.core import seed
from backend.database import Base
# Register mapped classes referenced by seed imports before the fixture creates
# any ORM instance. This mirrors the application's model bootstrap.
from backend.models import (  # noqa: F401
    campaign,
    chatbot,
    coupon,
    customer,
    delivery,
    loyalty,
    order,
    payment,
    product,
    product_promotion,
    promotion,
    salao,
    shipping,
)
from backend.models.admin import AdminUser
from backend.models.platform_rbac import PlatformRole, PlatformUserRole
from backend.models.rbac import Role, RbacModule, RbacPermission, RolePermission
from backend.models.tenant import Tenant


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__,
            AdminUser.__table__,
            PlatformRole.__table__,
            PlatformUserRole.__table__,
            Role.__table__,
            RbacModule.__table__,
            RbacPermission.__table__,
            RolePermission.__table__,
        ],
    )
    with engine.begin() as connection:
        # This constraint exists in PostgreSQL but is not declared by the ORM.
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX uq_role_module_perm "
            "ON role_permissions(role_id, module_id, permission_id)"
        )

    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(Tenant(
        id=seed.LEGACY_TENANT_ID,
        slug="legacy",
        name="Empresa Legada",
        status="active",
        timezone="America/Sao_Paulo",
        locale="pt-BR",
        is_legacy=True,
    ))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _rbac_ids(db):
    return {
        "roles": {row.name: row.id for row in db.query(Role).all()},
        "modules": {row.key: row.id for row in db.query(RbacModule).all()},
        "permissions": {
            row.key: row.id for row in db.query(RbacPermission).all()
        },
        "role_permissions": {
            (row.role_id, row.module_id, row.permission_id): row.id
            for row in db.query(RolePermission).all()
        },
    }


def _expected_role_permission_keys(db):
    roles = {
        row.name: row.id
        for row in db.query(Role).filter(
            Role.tenant_id == seed.LEGACY_TENANT_ID
        ).all()
    }
    modules = {row.key: row.id for row in db.query(RbacModule).all()}
    permissions = {
        row.key: row.id for row in db.query(RbacPermission).all()
    }
    return {
        (roles[role_name], modules[module_key], permissions[permission_key])
        for role_name, module_permissions in seed._ROLE_PERMISSIONS.items()
        for module_key, permission_keys in module_permissions.items()
        for permission_key in permission_keys
    }


def test_rbac_seed_reuses_migration_modules_and_is_idempotent(db):
    migrated_module_ids = {
        key: f"migration-module-{key}"
        for key in ("whatsapp_gateway", "inventory", "cmv", "finance", "fiscal")
    }
    db.add_all([
        RbacModule(
            id=module_id,
            key=key,
            name=f"stale-{key}",
            order_index=-1,
            is_active=False,
        )
        for key, module_id in migrated_module_ids.items()
    ])
    db.commit()

    seed._seed_rbac(db)
    db.commit()

    first_ids = _rbac_ids(db)
    for key, module_id in migrated_module_ids.items():
        assert first_ids["modules"][key] == module_id
    assert len(first_ids["roles"]) == len(seed._ROLES)
    assert len(first_ids["modules"]) == len(seed._MODULES)
    assert len(first_ids["permissions"]) == len(seed._PERMISSIONS)
    assert set(first_ids["role_permissions"]) == _expected_role_permission_keys(db)

    seed._seed_rbac(db)
    db.commit()

    assert _rbac_ids(db) == first_ids


def test_rbac_seed_completes_partial_graph_without_overwriting_allowed(db):
    master = Role(
        id="existing-role-master",
        tenant_id=seed.LEGACY_TENANT_ID,
        name="master",
        description="incompleto",
        is_system=False,
    )
    whatsapp_gateway = RbacModule(
        id="existing-module-whatsapp-gateway",
        key="whatsapp_gateway",
        name="WhatsApp antigo",
        order_index=-1,
        is_active=False,
    )
    view = RbacPermission(
        id="existing-permission-view",
        key="view",
        name="Leitura antiga",
    )
    relation = RolePermission(
        id="existing-role-permission",
        tenant_id=seed.LEGACY_TENANT_ID,
        role_id=master.id,
        module_id=whatsapp_gateway.id,
        permission_id=view.id,
        allowed=False,
    )
    db.add_all([master, whatsapp_gateway, view, relation])
    db.commit()

    seed._seed_rbac(db)
    db.commit()

    preserved_relation = db.query(RolePermission).filter(
        RolePermission.role_id == master.id,
        RolePermission.module_id == whatsapp_gateway.id,
        RolePermission.permission_id == view.id,
    ).one()
    assert preserved_relation.id == relation.id
    assert preserved_relation.allowed is False
    assert whatsapp_gateway.id == "existing-module-whatsapp-gateway"
    assert view.id == "existing-permission-view"
    assert set(_rbac_ids(db)["role_permissions"]) == _expected_role_permission_keys(db)


def test_rbac_seed_allows_same_role_name_in_another_tenant_on_composite_schema(db):
    db.add_all([
        Tenant(
            id="tenant-other",
            slug="other",
            name="Outra empresa",
            status="active",
            timezone="America/Sao_Paulo",
            locale="pt-BR",
        ),
        Role(
            id="other-tenant-cozinha",
            tenant_id="tenant-other",
            name="cozinha",
            description="Cozinha de outra empresa",
            is_system=True,
        ),
    ])
    db.commit()

    seed._seed_rbac(db)
    db.commit()

    assert db.query(Role).filter_by(
        tenant_id=seed.LEGACY_TENANT_ID,
        name="cozinha",
    ).count() == 1
    assert db.query(Role).filter_by(
        tenant_id="tenant-other",
        name="cozinha",
    ).count() == 1
    other_role = db.query(Role).filter_by(id="other-tenant-cozinha").one()
    assert other_role.description == "Cozinha de outra empresa"
    assert other_role.is_system is True


def test_rbac_seed_fails_closed_when_roles_name_is_still_globally_unique(db):
    db.add_all([
        Tenant(
            id="tenant-other",
            slug="other",
            name="Outra empresa",
            status="active",
            timezone="America/Sao_Paulo",
            locale="pt-BR",
        ),
        Role(
            id="other-tenant-cozinha",
            tenant_id="tenant-other",
            name="cozinha",
            description="Cozinha de outra empresa",
            is_system=True,
        ),
    ])
    db.commit()
    db.execute(text("CREATE UNIQUE INDEX roles_name_key ON roles(name)"))
    db.commit()

    with pytest.raises(RuntimeError, match="Role.name ainda e globalmente unico"):
        seed._seed_rbac(db)


def test_rbac_seed_fails_closed_when_composite_role_uniqueness_is_missing(db, monkeypatch):
    class InspectorWithoutRoleUniqueness:
        def get_unique_constraints(self, _table_name):
            return []

        def get_indexes(self, _table_name):
            return []

    monkeypatch.setattr(seed, "inspect", lambda _bind: InspectorWithoutRoleUniqueness())

    with pytest.raises(RuntimeError, match="falta unicidade composta"):
        seed._seed_rbac(db)


def test_rbac_seed_fails_closed_when_role_schema_cannot_be_inspected(db, monkeypatch):
    def raise_inspection_error(_bind):
        raise SQLAlchemyError("inspection unavailable")

    monkeypatch.setattr(seed, "inspect", raise_inspection_error)

    with pytest.raises(RuntimeError, match="Nao foi possivel validar"):
        seed._seed_rbac(db)


def test_admin_seed_creates_configured_admin_when_other_user_exists(
    db, monkeypatch
):
    platform_owner = PlatformRole(
        id="platform-role-owner",
        key="platform_owner",
        name="Proprietario da Plataforma",
        is_system=True,
    )
    db.add_all([
        platform_owner,
        AdminUser(
            id="other-admin",
            email="other@example.com",
            name="Outro",
            password_hash="existing-hash",
        ),
    ])
    db.commit()
    monkeypatch.setenv("ADMIN_EMAIL", "owner@example.com")
    monkeypatch.setenv("ADMIN_NAME", "Owner")
    monkeypatch.setenv("ADMIN_PASSWORD", "safe-test-password")

    with patch(
        "backend.core.security.hash_password",
        return_value="new-hash",
    ) as hash_password:
        seed._seed_admin(db)
        db.commit()

    owner = db.query(AdminUser).filter(
        AdminUser.email == "owner@example.com"
    ).one()
    assert owner.name == "Owner"
    assert owner.password_hash == "new-hash"
    hash_password.assert_called_once_with("safe-test-password")
    assert db.query(PlatformUserRole).filter(
        PlatformUserRole.user_id == owner.id,
        PlatformUserRole.role_id == platform_owner.id,
    ).count() == 1


def test_admin_seed_repairs_owner_link_without_changing_existing_password(
    db, monkeypatch
):
    platform_owner = PlatformRole(
        id="platform-role-owner",
        key="platform_owner",
        name="Proprietario da Plataforma",
        is_system=True,
    )
    owner = AdminUser(
        id="configured-admin",
        email="owner@example.com",
        name="Nome existente",
        password_hash="keep-this-hash",
    )
    db.add_all([platform_owner, owner])
    db.commit()
    monkeypatch.setenv("ADMIN_EMAIL", owner.email)
    monkeypatch.setenv("ADMIN_NAME", "Nome novo ignorado")
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    seed._seed_admin(db)
    db.flush()
    seed._seed_admin(db)
    db.commit()

    assert owner.name == "Nome existente"
    assert owner.password_hash == "keep-this-hash"
    assert db.query(PlatformUserRole).filter(
        PlatformUserRole.user_id == owner.id,
        PlatformUserRole.role_id == platform_owner.id,
    ).count() == 1
