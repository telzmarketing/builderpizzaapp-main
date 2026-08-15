"""Allowlisted projection of the authenticated platform operator session."""
from sqlalchemy.orm import Session

from backend.models.platform_rbac import (
    PlatformPermission,
    PlatformRole,
    PlatformRolePermission,
    PlatformUserRole,
)


class PlatformSessionService:
    def __init__(self, db: Session):
        self.db = db

    def get_session(self, user_id: str) -> dict:
        roles = (
            self.db.query(PlatformRole.key, PlatformRole.name)
            .join(PlatformUserRole, PlatformUserRole.role_id == PlatformRole.id)
            .filter(PlatformUserRole.user_id == user_id)
            .order_by(PlatformRole.key.asc())
            .all()
        )
        permissions = (
            self.db.query(PlatformPermission.key)
            .join(
                PlatformRolePermission,
                PlatformRolePermission.permission_id == PlatformPermission.id,
            )
            .join(
                PlatformUserRole,
                PlatformUserRole.role_id == PlatformRolePermission.role_id,
            )
            .filter(PlatformUserRole.user_id == user_id)
            .distinct()
            .order_by(PlatformPermission.key.asc())
            .all()
        )
        return {
            "user_id": user_id,
            "roles": [{"key": role.key, "name": role.name} for role in roles],
            "permissions": [permission.key for permission in permissions],
        }
