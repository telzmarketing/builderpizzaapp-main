from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GestaoModuleSettingsOut(BaseModel):
    id: str
    tenant_id: str
    module_key: str
    title: str
    description: str
    enabled: bool
    status: str
    settings: dict[str, Any]
    notes: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GestaoModuleSettingsUpdate(BaseModel):
    enabled: bool | None = None
    status: str | None = Field(default=None, pattern=r"^(disabled|setup|ready|active)$")
    settings: dict[str, Any] | None = None
    notes: str | None = None
