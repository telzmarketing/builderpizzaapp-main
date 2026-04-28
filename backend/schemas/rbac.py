"""Pydantic schemas for RBAC — roles, modules, permissions, audit logs."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── Roles ─────────────────────────────────────────────────────────────────────

class RoleOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    is_system: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


# ── Modules ───────────────────────────────────────────────────────────────────

class ModuleOut(BaseModel):
    id: str
    key: str
    name: str
    description: Optional[str] = None
    parent_id: Optional[str] = None
    order_index: int
    is_active: bool
    model_config = {"from_attributes": True}


# ── Permissions ───────────────────────────────────────────────────────────────

class PermissionOut(BaseModel):
    id: str
    key: str
    name: str
    description: Optional[str] = None
    model_config = {"from_attributes": True}


# ── Permission matrix ─────────────────────────────────────────────────────────

class PermissionEntry(BaseModel):
    module_id: str
    permission_id: str
    allowed: bool


class RolePermissionsUpdate(BaseModel):
    permissions: list[PermissionEntry]


class UserPermissionsUpdate(BaseModel):
    permissions: list[PermissionEntry]


# ── Effective permissions (returned to frontend) ──────────────────────────────

class EffectivePermissions(BaseModel):
    is_master: bool
    role_id: Optional[str] = None
    role_name: Optional[str] = None
    # {module_key: {perm_key: bool}}
    modules: dict[str, dict[str, bool]]


# ── Audit logs ────────────────────────────────────────────────────────────────

class AuditLogOut(BaseModel):
    id: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    action: str
    module_key: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}
