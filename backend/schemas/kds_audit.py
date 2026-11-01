from datetime import datetime
from pydantic import BaseModel, Field


class AuditItemConfirmIn(BaseModel):
    confirmed_quantity: int = Field(ge=0)


class AuditVolumeConfirmIn(BaseModel):
    confirmed: bool = True


class AuditEvidenceIn(BaseModel):
    asset_id: str = Field(min_length=1, max_length=64)
    evidence_type: str = Field(default="handoff", min_length=1, max_length=40)
    captured_at: datetime | None = None
    metadata_json: str | None = Field(default=None, max_length=4000)


class AuditHandoffIn(BaseModel):
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)

