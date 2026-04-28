"""RBAC models — Role, RbacModule, RbacPermission, RolePermission, UserPermission, AdminAuditLog."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from backend.database import Base


class Role(Base):
    __tablename__ = "roles"

    id          = Column(String, primary_key=True)
    name        = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    is_system   = Column(Boolean, default=False)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))


class RbacModule(Base):
    __tablename__ = "rbac_modules"

    id          = Column(String, primary_key=True)
    key         = Column(String(50), unique=True, nullable=False)
    name        = Column(String(100), nullable=False)
    description = Column(Text)
    parent_id   = Column(String, ForeignKey("rbac_modules.id", ondelete="SET NULL"), nullable=True)
    order_index = Column(Integer, default=0)
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class RbacPermission(Base):
    __tablename__ = "rbac_permissions"

    id          = Column(String, primary_key=True)
    key         = Column(String(30), unique=True, nullable=False)
    name        = Column(String(100), nullable=False)
    description = Column(Text)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id            = Column(String, primary_key=True)
    role_id       = Column(String, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    module_id     = Column(String, ForeignKey("rbac_modules.id", ondelete="CASCADE"), nullable=False)
    permission_id = Column(String, ForeignKey("rbac_permissions.id", ondelete="CASCADE"), nullable=False)
    allowed       = Column(Boolean, default=True)


class UserPermission(Base):
    __tablename__ = "user_permissions"

    id             = Column(String, primary_key=True)
    user_id        = Column(String, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False)
    module_id      = Column(String, ForeignKey("rbac_modules.id", ondelete="CASCADE"), nullable=False)
    permission_id  = Column(String, ForeignKey("rbac_permissions.id", ondelete="CASCADE"), nullable=False)
    allowed        = Column(Boolean, default=True)
    overrides_role = Column(Boolean, default=True)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id          = Column(String, primary_key=True)
    user_id     = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    user_name   = Column(String(200))
    action      = Column(String(50), nullable=False)
    module_key  = Column(String(50))
    entity_type = Column(String(100))
    entity_id   = Column(String(100))
    old_value   = Column(Text)
    new_value   = Column(Text)
    ip_address  = Column(String(50))
    user_agent  = Column(Text)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
