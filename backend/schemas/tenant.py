from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TenantOut(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TenantMembershipOut(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    role: str
    status: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TenantSelectionIn(BaseModel):
    """A requested tenant selection; authorization is always server-side."""

    tenant_id: str = Field(min_length=1, max_length=36)


class TenantContextOut(BaseModel):
    tenant_id: str
    source: str
    membership_id: str | None = None
