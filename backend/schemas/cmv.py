from __future__ import annotations

from pydantic import BaseModel


class CmvIngredientCostOut(BaseModel):
    inventory_item_id: str
    inventory_item_name: str | None = None
    unit_symbol: str | None = None
    quantity: float
    waste_percent: float
    unit_cost: float
    total_cost: float
    cost_source: str
    missing_cost: bool


class CmvRecipeCostOut(BaseModel):
    recipe_id: str
    version_number: int
    scope_label: str
    product_size_id: str | None = None
    product_crust_type_id: str | None = None
    product_drink_variant_id: str | None = None
    complement_key: str | None = None
    cost_total: float
    missing_cost: bool
    ingredients: list[CmvIngredientCostOut]


class CmvProductCostOut(BaseModel):
    product_id: str
    product_name: str
    product_type: str | None = None
    sale_price: float
    recipe_count: int
    has_recipe: bool
    missing_cost: bool
    cost_min: float
    cost_max: float
    cmv_percent_min: float | None = None
    cmv_percent_max: float | None = None
    margin_min: float
    margin_max: float
    status: str
    recipes: list[CmvRecipeCostOut]


class CmvOverviewOut(BaseModel):
    module_enabled: bool
    module_status: str
    dre_status: str
    dre_label: str
    operational_snapshot_count: int
    operational_sale_total: float
    operational_cost_total: float
    operational_cmv_percent: float | None = None
    operational_pending_count: int
    products_total: int
    products_with_recipe: int
    products_missing_recipe: int
    products_missing_cost: int
    average_cmv_percent: float | None = None
    products: list[CmvProductCostOut]
