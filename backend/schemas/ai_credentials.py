from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TenantAICredentialUpdate(BaseModel):
    provider: Literal["openai", "claude"]
    api_key: str = Field(min_length=1, max_length=500)


class TenantAICredentialOut(BaseModel):
    provider: Literal["openai", "claude"] | None = None
    configured: bool
    key_preview: str | None = None
    source: Literal["central", "environment", "legacy", "none"]
    centralized: bool = True
