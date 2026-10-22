from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Strict(BaseModel): model_config = ConfigDict(extra="forbid")
class RecipeItemIn(Strict): item_id: str = Field(min_length=1); unit_id: str = Field(min_length=1); quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6); position: int = Field(default=0, ge=0)
class RecipeIn(Strict): name: str = Field(min_length=1, max_length=180); output_item_id: str; output_unit_id: str; yield_quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6); instructions: str | None = None; items: list[RecipeItemIn] = Field(min_length=1, max_length=100); expected_version: int = Field(default=0, ge=0)
class RecipeOut(BaseModel): id: str; name: str; output_item_id: str; output_unit_id: str; yield_quantity: str; version_number: int; active: bool
class PreparationOrderIn(Strict): recipe_id: str; target_quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6); scheduled_for: datetime | None = None; notes: str | None = None; expected_version: int = Field(default=0, ge=0)
class PreparationCommandIn(Strict): expected_version: int = Field(ge=0); reason: str | None = Field(default=None, max_length=300)
class PreparationReportIn(Strict):
    expected_version: int = Field(ge=0)
    produced_quantity: Decimal = Field(default=Decimal(0), ge=0, max_digits=20, decimal_places=6)
    approved_quantity: Decimal = Field(default=Decimal(0), ge=0, max_digits=20, decimal_places=6)
    lost_quantity: Decimal = Field(default=Decimal(0), ge=0, max_digits=20, decimal_places=6)
    discarded_quantity: Decimal = Field(default=Decimal(0), ge=0, max_digits=20, decimal_places=6)
    output_lot_id: str | None = None
    input_allocations: list[dict] = Field(default_factory=list)
    losses: list[dict] = Field(default_factory=list)
    reason: str | None = Field(default=None, max_length=300)
    prepared_at: datetime | None = None
    notes: str | None = None
class PreparationOrderOut(BaseModel): id: str; recipe_id: str; target_quantity: str; produced_quantity: str; lost_quantity: str; discarded_quantity: str; status: str; version: int
