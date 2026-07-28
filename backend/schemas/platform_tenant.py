from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.services.tenant_service import normalize_tenant_slug


class PlatformTenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=1, max_length=100)
    legal_name: str | None = Field(default=None, max_length=250)
    timezone: str = Field(default="America/Sao_Paulo", max_length=80)
    locale: str = Field(default="pt-BR", max_length=20)

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        return normalize_tenant_slug(value)


class PlatformTenantStatusUpdate(BaseModel):
    status: Literal["active", "suspended", "disabled"]


class PlatformTenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    legal_name: str | None
    status: Literal["active", "suspended", "disabled"]
    timezone: str
    locale: str
    is_legacy: bool
    created_at: datetime
    updated_at: datetime
