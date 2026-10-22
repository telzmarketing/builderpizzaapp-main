"""Versioned technical recipes; no costs or physical inventory in these DTOs."""
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.schemas.inventory_foundation import PositiveQuantity, Quantity, Factor, Id

Role = Literal["flavor", "base", "crust", "addon", "packaging"]


class RecipeLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)
    inventory_item_id: Id
    quantity: PositiveQuantity | None = None
    unit_id: Id | None = None
    entered_quantity: PositiveQuantity | None = None
    entered_unit_id: Id | None = None
    position: int = Field(default=0, ge=0, le=1000)
    waste_percent: Quantity = "0"
    notes: str | None = Field(default=None, max_length=4000)
    public_name: str | None = Field(default=None, min_length=1, max_length=180)
    show_public: bool = False
    allow_removal: bool = False

    @model_validator(mode="after")
    def valid_line(self):
        if self.waste_percent > 100:
            raise ValueError("Perda percentual excede 100.")
        if (self.entered_quantity is None) != (self.entered_unit_id is None):
            raise ValueError("Quantidade e unidade digitadas devem ser informadas juntas.")
        if self.quantity is None and self.entered_quantity is None:
            raise ValueError("Informe quantidade base ou quantidade/unidade digitadas.")
        if self.show_public and not self.public_name:
            raise ValueError("Ingrediente publico exige nome comercial autorizado.")
        return self


class RecipePublishIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)
    expected_version: int = Field(ge=0)
    component_role: Role = "flavor"
    reference_fraction: Factor = "1"
    product_size_id: Id | None = None
    product_crust_type_id: Id | None = None
    product_drink_variant_id: Id | None = None
    complement_key: str | None = Field(default=None, min_length=1, max_length=120)
    complement_name: str | None = Field(default=None, max_length=180)
    active: bool = True
    notes: str | None = Field(default=None, max_length=4000)
    instructions: str | None = Field(default=None, max_length=16000)
    preparation_steps: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(default_factory=list, max_length=100)
    reference_image_url: str | None = Field(default=None, max_length=700)
    items: list[RecipeLineIn] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def fraction(self):
        if self.reference_fraction > 1:
            raise ValueError("Fracao de referencia deve ser no maximo uma unidade.")
        if self.component_role != "flavor" and self.reference_fraction != 1:
            raise ValueError("Componente comum tem referencia de uma unidade inteira.")
        return self


class RecipeArchiveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class CompositionCustomization(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["remove", "substitute"]
    inventory_item_id: Id
    scope_product_id: Id | None = None
    scope_component_role: Role | None = None
    replacement_recipe_id: Id | None = None

    @model_validator(mode="after")
    def substitution(self):
        if (self.action == "substitute") != bool(self.replacement_recipe_id):
            raise ValueError("Somente substituicao exige versao de receita adicional selecionada.")
        return self


class CompositionFlavorIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: Id
    fraction: Factor | None = None


class CompositionPreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: Id
    quantity: int = Field(default=1, ge=1, le=1000)
    selected_size_id: Id | None = None
    selected_crust_type_id: Id | None = None
    selected_border_id: Id | None = None
    selected_drink_variant_id: Id | None = None
    flavors: list[CompositionFlavorIn] = Field(default_factory=list, max_length=3)
    add_ons: list[Id] = Field(default_factory=list, max_length=30)
    customizations: list[CompositionCustomization] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def explicit_fractions(self):
        fractions = [flavor.fraction for flavor in self.flavors]
        if any(f is not None for f in fractions):
            if not all(f is not None for f in fractions) or sum(fractions, Decimal(0)) != 1:
                raise ValueError("Fracoes explicitas devem estar completas e somar um.")
        return self


class RecipeLineOut(BaseModel):
    id: str
    inventory_item_id: str
    inventory_item_name: str
    quantity: str
    unit_id: str | None
    unit_symbol: str | None
    entered_quantity: str | None
    entered_unit_id: str | None
    conversion_factor_snapshot: str | None
    position: int
    waste_percent: str
    notes: str | None
    public_name: str | None
    show_public: bool
    allow_removal: bool


class RecipeV1Out(BaseModel):
    id: str
    product_id: str
    version_number: int
    component_role: Role
    reference_fraction: str
    product_size_id: str | None
    product_crust_type_id: str | None
    product_drink_variant_id: str | None
    complement_key: str | None
    complement_name: str | None
    active: bool
    notes: str | None
    instructions: str | None
    preparation_steps: list[str]
    reference_image_url: str | None
    items: list[RecipeLineOut]
    created_at: str | None


class RecipePageOut(BaseModel):
    items: list[RecipeV1Out]
    latest_version: int
    next_cursor: str | None = None


class CompositionIngredientOut(BaseModel):
    inventory_item_id: str
    name: str
    quantity: str
    unit_id: str | None
    unit_symbol: str | None
    recipe_version_id: str | None
    component_role: str
    scope_product_id: str | None
    position: int
    waste_percent: str


class CompositionFlavorOut(BaseModel):
    product_id: str
    name: str
    fraction: str
    ingredients: list[CompositionIngredientOut]


class RecipeMethodOut(BaseModel):
    recipe_version_id: str
    instructions: str | None
    preparation_steps: list[str]
    reference_image_url: str | None


class CompositionOut(BaseModel):
    product_id: str
    quantity: int
    complete: bool
    missing: list[str]
    recipe_version_ids: list[str]
    common_components: list[CompositionIngredientOut]
    flavors: list[CompositionFlavorOut]
    ingredients: list[CompositionIngredientOut]
    removed_ingredients: list[CompositionIngredientOut]
    substitutions: list[CompositionCustomization]
    methods: list[RecipeMethodOut]
    notes: str | None


class PublicRecipeIngredientsOut(BaseModel):
    ingredients: list[str]
