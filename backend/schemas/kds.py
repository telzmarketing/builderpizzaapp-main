from __future__ import annotations

from pydantic import BaseModel, Field


class DispatchAssignIn(BaseModel):
    delivery_person_id: str = Field(min_length=1, max_length=100)
    estimated_minutes: int = Field(default=40, ge=1, le=240)
