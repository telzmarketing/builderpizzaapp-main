from typing import Literal

from pydantic import BaseModel


class AIModelOut(BaseModel):
    id: str
    name: str
    provider: Literal["openai", "claude"] | None = None
    owned_by: str | None = None
    created_at: str | None = None


class AIModelsOut(BaseModel):
    provider: Literal["openai", "claude"]
    models: list[AIModelOut]
    source: Literal["provider", "empty"] = "provider"
    credential_source: Literal["central"] | None = None

