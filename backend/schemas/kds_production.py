from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from datetime import datetime

class KdsCommandIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    reason: str | None = Field(default=None, min_length=1, max_length=300)

class KdsCheckIn(KdsCommandIn):
    approved: bool

class KdsPresenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requested_state: Literal["available", "paused", "offline"] | None = None
    state: Literal["available", "paused", "offline", "in_production"] | None = None
    station_id: str = Field(default="cozinha", min_length=1, max_length=80)
    expected_version: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=300)

    @property
    def effective_state(self):
        return "available" if self.state == "in_production" else (self.requested_state or self.state or "offline")

class KdsHeartbeatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operational_session_id: str = Field(default="kds-session", min_length=1, max_length=120)
    station_id: str = Field(default="cozinha", min_length=1, max_length=80)
    expected_version: int = Field(ge=0)

class KdsRedistributionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_ids: list[str] = Field(min_length=1, max_length=100)
    task_versions: dict[str, int] = Field(default_factory=dict)
    expected_versions: dict[str, int] = Field(default_factory=dict)
    target_operator_id: str | None = Field(default=None, min_length=1)
    to_operator_id: str | None = Field(default=None, min_length=1)
    from_operator_id: str | None = Field(default=None, min_length=1)
    reason: str = Field(min_length=1, max_length=300)
    expected_version: int = Field(default=0, ge=0)

    @property
    def effective_versions(self):
        return self.task_versions or self.expected_versions

    @property
    def effective_target_operator_id(self):
        return self.target_operator_id or self.to_operator_id or ""

class KdsTaskOut(BaseModel):
    task_id: str; production_unit_id: str; order_id: str; order_item_id: str
    unit_index: int; attempt_id: str; attempt_number: int; state: str
    version: int; operator_id: str | None = None; requires_oven: bool
    assigned_at: datetime | None = None; started_at: datetime | None = None
    assembly_finished_at: datetime | None = None; completed_at: datetime | None = None
