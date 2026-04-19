from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime


class HomeCatalogConfigOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    mode: str
    selected_categories: str   # JSON string — parse on client
    selected_product_ids: str  # JSON string — parse on client
    show_promotions: bool
    updated_at: datetime


class HomeCatalogConfigUpdate(BaseModel):
    mode: Optional[str] = None           # "all" | "categories" | "products"
    selected_categories: Optional[List[str]] = None
    selected_product_ids: Optional[List[str]] = None
    show_promotions: Optional[bool] = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("all", "categories", "products"):
            raise ValueError("mode must be 'all', 'categories', or 'products'")
        return v
