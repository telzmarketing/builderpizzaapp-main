"""Public contracts for the transversal automation core."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AutomationTriggerInput(BaseModel):
    key: str
    config: dict[str, Any] = Field(default_factory=dict)


class AutomationConditionInput(BaseModel):
    key: str = "field"
    field: str
    operator: str
    value: Any = None


class AutomationActionInput(BaseModel):
    key: str
    config: dict[str, Any] = Field(default_factory=dict)


class AutomationDefinitionInput(BaseModel):
    trigger: AutomationTriggerInput
    conditions: list[AutomationConditionInput] = Field(default_factory=list)
    actions: list[AutomationActionInput] = Field(default_factory=list)


class AutomationSimulationInput(AutomationDefinitionInput):
    sample_event_id: str | None = None
    sample_payload: dict[str, Any] = Field(default_factory=dict)


class AutomationProcessInput(BaseModel):
    limit: int = Field(default=25, ge=1, le=100)
    worker_id: str | None = Field(default=None, max_length=120)
