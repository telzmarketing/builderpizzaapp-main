from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


PortionUsage = Literal["mandatory", "optional", "direct"]


class InventoryPortionConfigIn(BaseModel):
    source_item_id: str = Field(min_length=1, max_length=120)
    usage: PortionUsage = "mandatory"
    portion_weight: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    unit_id: str = Field(min_length=1, max_length=120)
    reference_fraction: Decimal = Field(default=Decimal("1"), gt=0, le=1, max_digits=20, decimal_places=12)
    size: str | None = Field(default=None, max_length=80)
    min_stock: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=6)
    target_stock: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=6)
    shelf_life_days: int | None = Field(default=None, ge=0, le=3650)
    yield_percent: Decimal = Field(default=Decimal("100"), gt=0, le=100, max_digits=8, decimal_places=4)
    loss_percent: Decimal = Field(default=Decimal("0"), ge=0, lt=100, max_digits=8, decimal_places=4)
    active: bool = True

    @model_validator(mode="after")
    def validate_stock_levels(self):
        if self.target_stock < self.min_stock:
            raise ValueError("target_stock deve ser maior ou igual a min_stock")
        return self


class InventoryPortionConfigOut(InventoryPortionConfigIn):
    id: str
    tenant_id: str
    output_item_id: str
    output_item_name: str | None = None
    output_item_sku: str | None = None
    source_item_name: str | None = None
    unit_symbol: str | None = None
    version: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class InventoryPortionPrepareIn(BaseModel):
    target_quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    scheduled_for: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)
    expected_version: int = Field(default=0, ge=0)


class InventoryPortionBalanceOut(BaseModel):
    config_id: str
    output_item_id: str
    output_item_name: str
    source_item_name: str | None = None
    unit_symbol: str | None = None
    physical_stock: Decimal
    reserved_stock: Decimal
    available_stock: Decimal
    in_preparation: Decimal
    min_stock: Decimal
    target_stock: Decimal
    active: bool


class InventoryPortionReplenishmentOut(BaseModel):
    config_id: str
    output_item_id: str
    output_item_name: str
    source_item_name: str | None = None
    unit_symbol: str | None = None
    available_stock: Decimal
    in_preparation: Decimal
    min_stock: Decimal
    target_stock: Decimal
    suggested_portions: Decimal
    estimated_source_quantity: Decimal
    status: Literal["ok", "alert"]
