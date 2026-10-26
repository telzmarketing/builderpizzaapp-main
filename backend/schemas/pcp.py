from datetime import date
from pydantic import BaseModel, Field


class PcpPlanGenerateIn(BaseModel):
    week_start: date
    source_weeks: int = Field(default=4, ge=1, le=52)


class PcpPlanApprovalIn(BaseModel):
    expected_status: str = "draft"


class PcpPlanOut(BaseModel):
    id: str
    tenant_id: str
    week_start: date
    status: str
    source_window_start: date
    source_window_end: date
    suggestions: list[dict]
    approved_by: str | None = None
    approved_at: object | None = None
