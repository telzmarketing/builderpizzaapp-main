from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductSizeAssociationCreate(BaseModel):
    global_size_id: str = Field(min_length=1, max_length=36)
    price: float = Field(gt=0)
    label: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=200)
    is_default: bool = False
    sort_order: int = Field(default=0, ge=0)
    active: bool = True


class ProductOptionAssociationCreate(BaseModel):
    global_dough_type_id: str | None = Field(default=None, min_length=1, max_length=36)
    global_crust_id: str | None = Field(default=None, min_length=1, max_length=36)
    price_addition_override: float | None = Field(default=None, ge=0)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0)
    active: bool = True


class ProductCatalogConfigurationOut(BaseModel):
    product_id: str
    sizes: list[str]
    size_prices: dict[str, float] = Field(default_factory=dict)
    dough_types: list[str]
    crusts: list[str]


class ProductCatalogConfigurationUpdate(BaseModel):
    sizes: list[str] = Field(default_factory=list)
    size_prices: dict[str, float] = Field(default_factory=dict)
    dough_types: list[str] = Field(default_factory=list)
    crusts: list[str] = Field(default_factory=list)

    @field_validator("size_prices")
    @classmethod
    def validate_size_prices(cls, value):
        if any(price <= 0 for price in value.values()):
            raise ValueError("Os precos dos tamanhos devem ser maiores que zero.")
        return value



class GlobalCatalogCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    price_addition: float = Field(default=0.0, ge=0, le=100000)
    sort_order: int = Field(default=0, ge=0)
    active: bool = True


class GlobalSizeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int = Field(default=0, ge=0)
    active: bool = True
    is_default: bool = False


class GlobalCatalogUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    price_addition: float | None = Field(default=None, ge=0, le=100000)
    sort_order: int | None = Field(default=None, ge=0)
    active: bool | None = None


class GlobalSizeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0)
    active: bool | None = None
    is_default: bool | None = None


class GlobalCatalogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    name: str
    description: str | None
    price_addition: float
    sort_order: int
    active: bool
    created_at: datetime
    updated_at: datetime


class GlobalSizeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    name: str
    description: str | None
    sort_order: int
    active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime
