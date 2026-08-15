"""Read-only API contracts for global platform users."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr


class PlatformRoleSummaryOut(BaseModel):
    id: str
    key: str
    name: str
    description: str | None = None
    is_system: bool


class PlatformUserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    active: bool
    status: Literal["active", "inactive"]
    phone: str | None = None
    job_title: str | None = None
    last_login_at: datetime | None = None
    force_password_change: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    platform_roles: list[PlatformRoleSummaryOut]
    membership_count: int


class PlatformUserPageOut(BaseModel):
    items: list[PlatformUserOut]
    total: int
    page: int
    page_size: int
    pages: int
