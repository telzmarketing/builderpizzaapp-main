from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

InventoryItemType = Literal["ingredient", "finished_good", "packaging", "supply"]
InventoryUnitType = Literal["unit", "mass", "volume", "package"]
InventoryPurchaseStatus = Literal["draft", "confirmed"]
InventoryMovementType = Literal["in", "out"]


class InventoryUnitIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    symbol: str = Field(min_length=1, max_length=20)
    unit_type: InventoryUnitType = "unit"
    active: bool = True


class InventoryUnitOut(InventoryUnitIn):
    id: str
    tenant_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class InventoryCategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    description: str | None = None
    active: bool = True


class InventoryCategoryOut(InventoryCategoryIn):
    id: str
    tenant_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class InventoryLocationIn(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    description: str | None = None
    active: bool = True


class InventoryLocationOut(InventoryLocationIn):
    id: str
    tenant_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class InventorySupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    document: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    active: bool = True


class InventorySupplierOut(InventorySupplierIn):
    id: str
    tenant_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class InventoryItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    sku: str | None = None
    item_type: InventoryItemType = "ingredient"
    category_id: str | None = None
    unit_id: str | None = None
    default_location_id: str | None = None
    min_stock: float = Field(default=0.0, ge=0)
    notes: str | None = None
    active: bool = True


class InventoryItemOut(InventoryItemIn):
    id: str
    tenant_id: str
    category_name: str | None = None
    unit_name: str | None = None
    unit_symbol: str | None = None
    default_location_name: str | None = None
    current_stock: float = 0.0
    available_stock: float = 0.0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InventoryPurchaseItemIn(BaseModel):
    item_id: str
    quantity: float = Field(gt=0)
    unit_cost: float = Field(default=0.0, ge=0)


class InventoryPurchaseIn(BaseModel):
    supplier_id: str | None = None
    status: InventoryPurchaseStatus = "draft"
    invoice_number: str | None = None
    expected_date: date | None = None
    notes: str | None = None
    items: list[InventoryPurchaseItemIn] = Field(default_factory=list)


class InventoryPurchaseItemOut(BaseModel):
    id: str
    purchase_id: str
    item_id: str
    item_name: str | None = None
    quantity: float
    unit_cost: float
    total_cost: float


class InventoryPurchaseOut(BaseModel):
    id: str
    tenant_id: str
    supplier_id: str | None = None
    supplier_name: str | None = None
    status: str
    invoice_number: str | None = None
    expected_date: date | None = None
    notes: str | None = None
    total_amount: float
    items: list[InventoryPurchaseItemOut] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InventoryManualEntryIn(BaseModel):
    item_id: str
    location_id: str | None = None
    movement_type: InventoryMovementType = "in"
    quantity: float = Field(gt=0)
    unit_cost: float = Field(default=0.0, ge=0)
    reason: str = Field(default="initial_stock", min_length=1, max_length=120)
    notes: str | None = None


class InventoryManualEntryOut(BaseModel):
    id: str
    tenant_id: str
    item_id: str
    item_name: str | None = None
    location_id: str | None = None
    location_name: str | None = None
    movement_type: str
    quantity: float
    unit_cost: float
    reason: str
    notes: str | None = None
    created_at: datetime | None = None


class InventoryStockMovementOut(BaseModel):
    id: str
    tenant_id: str
    item_id: str
    item_name: str | None = None
    location_id: str | None = None
    location_name: str | None = None
    source_type: str
    source_id: str | None = None
    movement_type: str
    quantity_delta: float
    unit_cost: float
    reason: str
    notes: str | None = None
    created_at: datetime | None = None


class InventoryStockBalanceOut(BaseModel):
    item_id: str
    item_name: str
    unit_symbol: str | None = None
    current_stock: float
    min_stock: float
    below_min_stock: bool
    active: bool


class InventoryRecipeItemIn(BaseModel):
    inventory_item_id: str
    quantity: float = Field(gt=0)
    waste_percent: float = Field(default=0.0, ge=0, le=100)
    notes: str | None = None


class InventoryRecipeVersionIn(BaseModel):
    product_size_id: str | None = None
    product_crust_type_id: str | None = None
    product_drink_variant_id: str | None = None
    complement_key: str | None = Field(default=None, max_length=120)
    complement_name: str | None = Field(default=None, max_length=180)
    active: bool = True
    notes: str | None = None
    items: list[InventoryRecipeItemIn] = Field(default_factory=list)


class InventoryRecipeItemOut(BaseModel):
    id: str
    recipe_id: str
    inventory_item_id: str
    inventory_item_name: str | None = None
    unit_symbol: str | None = None
    quantity: float
    waste_percent: float
    notes: str | None = None


class InventoryRecipeVersionOut(BaseModel):
    id: str
    tenant_id: str
    product_id: str
    product_name: str | None = None
    product_size_id: str | None = None
    product_size_label: str | None = None
    product_crust_type_id: str | None = None
    product_crust_type_name: str | None = None
    product_drink_variant_id: str | None = None
    product_drink_variant_name: str | None = None
    complement_key: str | None = None
    complement_name: str | None = None
    version_number: int
    active: bool
    notes: str | None = None
    items: list[InventoryRecipeItemOut] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InventoryOverviewOut(BaseModel):
    units: list[InventoryUnitOut]
    categories: list[InventoryCategoryOut]
    locations: list[InventoryLocationOut]
    suppliers: list[InventorySupplierOut]
    items: list[InventoryItemOut]
    purchases: list[InventoryPurchaseOut]
    manual_entries: list[InventoryManualEntryOut]
    movements: list[InventoryStockMovementOut]
    balances: list[InventoryStockBalanceOut]
