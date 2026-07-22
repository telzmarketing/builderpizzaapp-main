"""Explicit platform-level roles and permissions, separate from tenant RBAC."""
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from backend.database import Base


class PlatformRole(Base):
    __tablename__ = "platform_roles"
    id = Column(String, primary_key=True)
    key = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PlatformPermission(Base):
    __tablename__ = "platform_permissions"
    id = Column(String, primary_key=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class PlatformRolePermission(Base):
    __tablename__ = "platform_role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_platform_role_permissions_role_permission"),)
    id = Column(String, primary_key=True)
    role_id = Column(String, ForeignKey("platform_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id = Column(String, ForeignKey("platform_permissions.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class PlatformUserRole(Base):
    __tablename__ = "platform_user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_platform_user_roles_user_role"),)
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(String, ForeignKey("platform_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    granted_by = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
