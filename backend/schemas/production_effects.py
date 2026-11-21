"""Internal commands for production losses and staff meals (no HTTP surface)."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EffectCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=1000)


class ProductionLossIn(EffectCommand):
    attempt_id: str = Field(min_length=1, max_length=100)
    expected_version: int = Field(ge=1)


class ProductionReproductionIn(EffectCommand):
    loss_id: str = Field(min_length=1, max_length=100)


class OrderBonificationIn(EffectCommand):
    order_id: str = Field(min_length=1, max_length=100)
    beneficiary: str = Field(min_length=1, max_length=200)


class ProductionEffectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: Literal["loss", "reproduction", "bonification"]
    order_id: str
    attempt_id: str | None
    source_effect_id: str | None
    actor_id: str
    reason: str
    cost_total: Decimal
    discount_amount: Decimal
    snapshot_json: dict
    created_at: datetime


class ProductionEffectEnvelope(BaseModel):
    success: bool = True
    data: ProductionEffectOut
