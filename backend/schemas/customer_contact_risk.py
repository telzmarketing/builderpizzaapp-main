from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ContactRiskEventType = Literal[
    "contact_reported",
    "order_complaint",
    "whatsapp_blocked",
    "marketing_opt_out",
    "campaign_sent",
    "manual_adjustment",
    "manual_block",
    "contact_unblocked",
]


class ContactRiskEventCreate(BaseModel):
    event_type: ContactRiskEventType
    channel: Literal["whatsapp"] = "whatsapp"
    points_delta: int | None = Field(default=None, ge=-100, le=100)
    source_type: str = Field(default="admin", max_length=80)
    source_id: str | None = Field(default=None, max_length=255)
    dedupe_key: str | None = Field(default=None, max_length=255)
    occurred_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContactRiskOverride(BaseModel):
    action: Literal["set_score", "block", "unblock", "complaint", "reported", "opt_out", "whatsapp_blocked"]
    reason: str = Field(min_length=3, max_length=500)
    score: int | None = Field(default=None, ge=0, le=100)


class ContactRiskEventOut(BaseModel):
    id: str
    event_type: str
    points_delta: int
    score_before: int
    score_after: int
    blocks_contact: bool
    source_type: str
    source_id: str | None
    occurred_at: datetime
    metadata: dict[str, Any]


class ContactRiskOut(BaseModel):
    customer_id: str
    channel: str
    score: int
    risk_level: str
    is_blocked: bool
    block_reason: str | None
    blocked_at: datetime | None
    campaign_deliveries_15d: int
    last_event_at: datetime | None
    eligible_for_marketing: bool
    eligibility_reason: str | None
    events: list[ContactRiskEventOut] = Field(default_factory=list)
