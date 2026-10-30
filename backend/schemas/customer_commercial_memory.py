from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


MemoryType = Literal["preference", "avoidance", "purchase_pattern", "service_note"]
MemoryConfidence = Literal["low", "medium", "high"]


class CustomerCommercialMemoryIn(BaseModel):
    memory_key: str = Field(min_length=2, max_length=160)
    memory_type: MemoryType = "preference"
    value: str = Field(min_length=1, max_length=2000)
    source: str = Field(default="crm", min_length=2, max_length=40)
    confidence: MemoryConfidence = "medium"
    active: bool = True


class CustomerCommercialMemoryOut(CustomerCommercialMemoryIn):
    id: str
    tenant_id: str
    customer_id: str
    last_observed_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
