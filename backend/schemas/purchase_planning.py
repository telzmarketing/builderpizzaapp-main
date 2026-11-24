from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


PlanningState = Literal["confirmed", "pending", "estimated", "blocked", "unavailable"]
PlanningAction = Literal["covered", "purchase_required", "review_required"]


class PurchasePlanningNeedOut(BaseModel):
    item_id: str
    item_name: str
    unit_id: str | None
    unit_symbol: str | None
    source: Literal["direct", "portion"]
    source_item_id: str | None = None
    source_item_name: str | None = None
    current_stock: Decimal
    reserved_stock: Decimal
    available_stock: Decimal
    in_transit: Decimal
    minimum_stock: Decimal
    target_stock: Decimal
    suggested_quantity: Decimal
    state: PlanningState
    action: PlanningAction
    reason: str


class PurchasePlanningOut(BaseModel):
    tenant_id: str
    generated_at: str
    items: list[PurchasePlanningNeedOut]
    totals: dict[str, int]
