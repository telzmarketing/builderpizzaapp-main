"""Provision the tenant-scoped, single-surface KDS roles."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from backend.models.rbac import RbacModule, RbacPermission, Role, RolePermission


KDS_ROLE_MODULES = {
    "cozinha": "cozinha",
    "expedicao": "expedicao",
}


def ensure_tenant_kds_roles(db: Session, tenant_id: str) -> dict[str, Role]:
    modules = {
        row.key: row
        for row in db.query(RbacModule).filter(
            RbacModule.key.in_(set(KDS_ROLE_MODULES.values()))
        ).all()
    }
    permissions = {
        row.key: row
        for row in db.query(RbacPermission).filter(
            RbacPermission.key.in_(("view", "edit"))
        ).all()
    }
    if set(modules) != set(KDS_ROLE_MODULES.values()) or set(permissions) != {"view", "edit"}:
        raise RuntimeError("Catalogo RBAC do KDS ainda nao foi provisionado.")

    roles: dict[str, Role] = {}
    for role_name, module_key in KDS_ROLE_MODULES.items():
        role = db.query(Role).filter(
            Role.tenant_id == tenant_id,
            Role.name == role_name,
        ).first()
        if role is None:
            role = Role(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                name=role_name,
                description=(
                    "Cozinha - operacao exclusiva do KDS"
                    if role_name == "cozinha"
                    else "Expedicao - operacao exclusiva do KDS"
                ),
                is_system=True,
            )
            db.add(role)
            db.flush()
        else:
            role.is_system = True

        allowed_module = modules[module_key]
        # Exact allow-list: a station account must not inherit an old pedidos,
        # entregas or motoboys permission from prior seeds.
        stale = (
            db.query(RolePermission)
            .filter(
                RolePermission.tenant_id == tenant_id,
                RolePermission.role_id == role.id,
                RolePermission.module_id != allowed_module.id,
            )
            .all()
        )
        for row in stale:
            db.delete(row)

        for permission in permissions.values():
            row = db.query(RolePermission).filter(
                RolePermission.tenant_id == tenant_id,
                RolePermission.role_id == role.id,
                RolePermission.module_id == allowed_module.id,
                RolePermission.permission_id == permission.id,
            ).first()
            if row is None:
                db.add(RolePermission(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    role_id=role.id,
                    module_id=allowed_module.id,
                    permission_id=permission.id,
                    allowed=True,
                ))
            else:
                row.allowed = True
        roles[role_name] = role
    db.flush()
    return roles
