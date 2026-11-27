from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrategicCampaignAutomationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    campaign_id: str
    automation_key: str
    event_key: str
    channel: str
    name: str
    enabled: bool
    definition: dict[str, Any] = Field(default_factory=dict)
    generated_from: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class StrategicCampaignAutomationUpdate(BaseModel):
    enabled: bool | None = None
    definition: dict[str, Any] | None = None
