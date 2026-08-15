"""Read-only queries for identities allowed to operate the platform."""
from __future__ import annotations

import math

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.models.admin import AdminUser
from backend.models.membership import TenantMembership
from backend.models.platform_rbac import PlatformRole, PlatformUserRole


class PlatformUserService:
    def __init__(self, db: Session):
        self.db = db

    def list_users(
        self,
        *,
        page: int,
        page_size: int,
        q: str | None = None,
        status: str | None = None,
        role: str | None = None,
    ) -> dict:
        """List global platform users without exposing authentication fields."""
        platform_role_exists = (
            self.db.query(PlatformUserRole.id)
            .filter(PlatformUserRole.user_id == AdminUser.id)
            .exists()
        )
        query = self.db.query(AdminUser).filter(platform_role_exists)

        search = (q or "").strip()
        if search:
            term = f"%{search}%"
            query = query.filter(
                or_(AdminUser.name.ilike(term), AdminUser.email.ilike(term))
            )

        if status == "active":
            query = query.filter(AdminUser.active.is_(True))
        elif status == "inactive":
            query = query.filter(AdminUser.active.is_(False))

        role_key = (role or "").strip().lower()
        if role_key:
            matching_role_exists = (
                self.db.query(PlatformUserRole.id)
                .join(PlatformRole, PlatformRole.id == PlatformUserRole.role_id)
                .filter(
                    PlatformUserRole.user_id == AdminUser.id,
                    func.lower(PlatformRole.key) == role_key,
                )
                .exists()
            )
            query = query.filter(matching_role_exists)

        total = query.count()
        users = (
            query.order_by(
                func.lower(AdminUser.name).asc(),
                func.lower(AdminUser.email).asc(),
                AdminUser.id.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        user_ids = [user.id for user in users]
        roles_by_user: dict[str, list[dict]] = {user_id: [] for user_id in user_ids}
        memberships_by_user: dict[str, int] = {user_id: 0 for user_id in user_ids}

        if user_ids:
            role_rows = (
                self.db.query(PlatformUserRole.user_id, PlatformRole)
                .join(PlatformRole, PlatformRole.id == PlatformUserRole.role_id)
                .filter(PlatformUserRole.user_id.in_(user_ids))
                .order_by(
                    PlatformUserRole.user_id.asc(),
                    func.lower(PlatformRole.name).asc(),
                    PlatformRole.key.asc(),
                )
                .all()
            )
            for user_id, platform_role in role_rows:
                roles_by_user[user_id].append({
                    "id": platform_role.id,
                    "key": platform_role.key,
                    "name": platform_role.name,
                    "description": platform_role.description,
                    "is_system": bool(platform_role.is_system),
                })

            membership_rows = (
                self.db.query(
                    TenantMembership.user_id,
                    func.count(TenantMembership.id).label("membership_count"),
                )
                .filter(
                    TenantMembership.user_id.in_(user_ids),
                    TenantMembership.status != "revoked",
                )
                .group_by(TenantMembership.user_id)
                .all()
            )
            memberships_by_user.update({
                user_id: int(membership_count)
                for user_id, membership_count in membership_rows
            })

        return {
            "items": [
                self._public_user(
                    user,
                    platform_roles=roles_by_user[user.id],
                    membership_count=memberships_by_user[user.id],
                )
                for user in users
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": math.ceil(total / page_size) if total else 0,
        }

    @staticmethod
    def _public_user(
        user: AdminUser,
        *,
        platform_roles: list[dict],
        membership_count: int,
    ) -> dict:
        # Explicit allowlist keeps password_hash, auth_version and future secrets private.
        active = bool(user.active)
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "active": active,
            "status": "active" if active else "inactive",
            "phone": user.phone,
            "job_title": user.job_title,
            "last_login_at": user.last_login_at,
            "force_password_change": bool(user.force_password_change),
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "platform_roles": platform_roles,
            "membership_count": membership_count,
        }
