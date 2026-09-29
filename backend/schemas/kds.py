from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DispatchAssignIn(BaseModel):
    delivery_person_id: str = Field(min_length=1, max_length=100)
    estimated_minutes: int = Field(default=40, ge=1, le=240)


KdsOverviewStage = Literal[
    "waiting_kitchen",
    "preparing",
    "ready_unassigned",
    "assigned_waiting_departure",
    "in_route",
]


class KdsOverviewDeliveryOut(BaseModel):
    status: str
    driver_name: str | None = None


class KdsOverviewOrderOut(BaseModel):
    id: str
    order_code: str | None = None
    stage: KdsOverviewStage
    status: str
    fulfillment_type: str
    created_at: datetime
    status_started_at: datetime
    delivery: KdsOverviewDeliveryOut | None = None


class KdsOverviewCountersOut(BaseModel):
    waiting_kitchen: int = 0
    preparing: int = 0
    ready_unassigned: int = 0
    assigned_waiting_departure: int = 0
    in_route: int = 0
    drivers_available: int = 0
    drivers_busy: int = 0


class KdsOverviewOut(BaseModel):
    generated_at: datetime
    counters: KdsOverviewCountersOut
    orders: list[KdsOverviewOrderOut]


class KdsOverviewEnvelope(BaseModel):
    success: Literal[True] = True
    data: KdsOverviewOut
