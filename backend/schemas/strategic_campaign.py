from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.models.strategic_campaign import StrategicCampaignStatus


STRATEGIC_CAMPAIGN_SNAPSHOT_SCHEMA_VERSION = 1


class StrategicCommercialConfig(BaseModel):
    sales_mode: Literal["immediate", "preorder"] = "immediate"
    allow_when_store_closed: bool = False
    require_scheduled_order: bool = False
    min_lead_minutes: int = Field(default=0, ge=0, le=43200)
    max_lead_days: int | None = Field(default=None, ge=1, le=365)
    allowed_payment_methods: list[Literal["pix", "credit_card", "debit_card", "pay_on_delivery"]] = Field(default_factory=list)


class StrategicMarketingConfig(BaseModel):
    planned_budget: float | None = Field(default=None, ge=0)
    traffic_campaign_id: str | None = Field(default=None, max_length=120)
    attribution_window_days: int = Field(default=30, ge=1, le=90)


class StrategicCampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    commercial_name: str | None = Field(default=None, max_length=200)
    slug: str = Field(min_length=1, max_length=180)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    visual_config: dict[str, Any] = Field(default_factory=dict)
    commercial_config: StrategicCommercialConfig = Field(default_factory=StrategicCommercialConfig)
    marketing_config: StrategicMarketingConfig = Field(default_factory=StrategicMarketingConfig)


class StrategicCampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    commercial_name: str | None = Field(default=None, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = None
    status: StrategicCampaignStatus | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    visual_config: dict[str, Any] | None = None
    commercial_config: StrategicCommercialConfig | None = None
    marketing_config: StrategicMarketingConfig | None = None


class StrategicCampaignDuplicate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=180)


StrategicCatalogId = Annotated[str, Field(min_length=1, max_length=120)]


class StrategicOfferRestrictions(BaseModel):
    """Optional catalog constraints kept inside the existing offer config JSON."""

    size_ids: list[StrategicCatalogId] | None = None
    crust_ids: list[StrategicCatalogId] | None = None
    border_ids: list[StrategicCatalogId] | None = None
    drink_ids: list[StrategicCatalogId] | None = None
    option_ids: list[StrategicCatalogId] | None = None
    flavor_count: int | None = Field(default=None, ge=1, le=3)

    model_config = ConfigDict(extra="allow")

    @field_validator("size_ids", "crust_ids", "border_ids", "drink_ids", "option_ids")
    @classmethod
    def validate_unique_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("As restricoes da oferta nao podem conter IDs repetidos.")
        return value


class StrategicOfferComponentIn(BaseModel):
    subcategory_id: StrategicCatalogId
    quantity: int = Field(ge=1, le=100)
    allow_repeated_products: bool = True
    restrictions: StrategicOfferRestrictions | None = None


class StrategicOfferSelectionGroup(BaseModel):
    """Independent catalog reference used by mixed strategic offers."""

    category_id: StrategicCatalogId | None = None
    subcategory_ids: list[StrategicCatalogId] = Field(default_factory=list, max_length=100)
    product_ids: list[StrategicCatalogId] = Field(default_factory=list, max_length=100)
    quantity: int = Field(ge=1, le=100)

    @model_validator(mode="after")
    def validate_reference(self):
        if len(self.subcategory_ids) != len(set(self.subcategory_ids)):
            raise ValueError("O grupo nao pode repetir subcategorias.")
        if len(self.product_ids) != len(set(self.product_ids)):
            raise ValueError("O grupo nao pode repetir produtos.")
        if bool(self.subcategory_ids) == bool(self.product_ids):
            raise ValueError("O grupo deve informar subcategorias ou produtos diretos.")
        if self.product_ids and not self.category_id:
            raise ValueError("Produtos diretos exigem category_id.")
        return self


class StrategicOfferConfig(BaseModel):
    pricing_mode: Literal["catalog", "product_promotion", "strategic_price"] | None = None
    product_promotion_id: StrategicCatalogId | None = None
    restrictions: StrategicOfferRestrictions | None = None
    selection_groups: list[StrategicOfferSelectionGroup] | None = Field(default=None, max_length=100)

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def validate_pricing_reference(self):
        if self.pricing_mode == "product_promotion" and not self.product_promotion_id:
            raise ValueError("O modo product_promotion exige product_promotion_id.")
        if self.product_promotion_id and self.pricing_mode not in {None, "product_promotion"}:
            raise ValueError("product_promotion_id so pode ser usado com pricing_mode product_promotion.")
        return self


def _validated_offer_config(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    validated = StrategicOfferConfig.model_validate(value)
    return validated.model_dump(mode="python", exclude_none=True, exclude_unset=True)


class StrategicOfferCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    product_id: str | None = None
    kit_id: str | None = None
    reference_type: Literal["product", "kit", "subcategory", "mixed_subcategories"] | None = None
    components: list[StrategicOfferComponentIn] = Field(default_factory=list, max_length=100)
    selection_quantity: int | None = Field(default=None, ge=1, le=100)
    pricing_strategy: Literal["catalog", "percentage", "fixed_discount", "fixed_price"] = "catalog"
    discount_percent: Decimal | None = Field(default=None, gt=0, le=100, decimal_places=4)
    discount_amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    fixed_promotional_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    price_original: Decimal = Field(ge=0, decimal_places=2)
    price_promotional: Decimal = Field(ge=0, decimal_places=2)
    display_order: int = Field(default=0, ge=0)
    quantity_limit: int | None = Field(default=None, ge=0)
    max_per_customer: int | None = Field(default=None, ge=1)
    sales_starts_at: datetime | None = None
    sales_ends_at: datetime | None = None
    show_when_sold_out: bool = True
    button_text: str | None = Field(default=None, max_length=120)
    image_desktop_url: str | None = None
    image_mobile_url: str | None = None
    badge_text: str | None = Field(default=None, max_length=80)
    highlighted: bool = False
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("config")
    @classmethod
    def validate_config(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validated_offer_config(value) or {}

    @model_validator(mode="after")
    def validate_reference_and_price(self):
        inferred = self.reference_type or ("product" if self.product_id else "kit" if self.kit_id else None)
        if inferred in {"product", "kit"} and bool(self.product_id) == bool(self.kit_id):
            raise ValueError("Informe exatamente um produto ou kit para a oferta.")
        if inferred == "product" and (not self.product_id or self.kit_id or self.components):
            raise ValueError("A referencia product exige somente product_id.")
        if inferred == "kit" and (not self.kit_id or self.product_id or self.components):
            raise ValueError("A referencia kit exige somente kit_id.")
        selection_groups = self.config.get("selection_groups")
        has_selection_groups = bool(selection_groups)
        if inferred == "subcategory" and (self.product_id or self.kit_id or not self.components):
            raise ValueError("Ofertas por subcategoria exigem componentes e nao aceitam produto ou kit direto.")
        if inferred == "mixed_subcategories" and (self.product_id or self.kit_id or (not self.components and not has_selection_groups)):
            raise ValueError("Ofertas mistas exigem componentes ou grupos de escolha.")
        if inferred == "subcategory" and len(self.components) != 1:
            raise ValueError("A referencia subcategory exige exatamente um componente.")
        if inferred == "mixed_subcategories" and len(self.components) < 2 and not has_selection_groups:
            raise ValueError("A referencia mixed_subcategories exige ao menos dois componentes.")
        if not inferred:
            raise ValueError("Informe uma referencia valida para a oferta.")
        if len({item.subcategory_id for item in self.components}) != len(self.components):
            raise ValueError("A mesma subcategoria nao pode ser repetida na composicao.")
        self.reference_type = inferred
        values = {"percentage": self.discount_percent, "fixed_discount": self.discount_amount, "fixed_price": self.fixed_promotional_price}
        if self.pricing_strategy != "catalog" and values[self.pricing_strategy] is None:
            raise ValueError("A estrategia de preco exige seu valor correspondente.")
        if any(value is not None for key, value in values.items() if key != self.pricing_strategy):
            raise ValueError("Informe somente o valor da estrategia de preco selecionada.")
        if self.pricing_strategy == "catalog" and any(value is not None for value in values.values()):
            raise ValueError("A estrategia catalog nao aceita desconto estrategico.")
        if self.price_promotional > self.price_original:
            raise ValueError("O preço promocional não pode superar o preço original.")
        if self.sales_starts_at and self.sales_ends_at and self.sales_ends_at <= self.sales_starts_at:
            raise ValueError("O encerramento da oferta deve ser posterior ao início.")
        return self


class StrategicOfferUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    reference_type: Literal["product", "kit", "subcategory", "mixed_subcategories"] | None = None
    product_id: str | None = None
    kit_id: str | None = None
    components: list[StrategicOfferComponentIn] | None = Field(default=None, max_length=100)
    selection_quantity: int | None = Field(default=None, ge=1, le=100)
    pricing_strategy: Literal["catalog", "percentage", "fixed_discount", "fixed_price"] | None = None
    discount_percent: Decimal | None = Field(default=None, gt=0, le=100, decimal_places=4)
    discount_amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    fixed_promotional_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    price_original: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    price_promotional: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    active: bool | None = None
    display_order: int | None = Field(default=None, ge=0)
    quantity_limit: int | None = Field(default=None, ge=0)
    max_per_customer: int | None = Field(default=None, ge=1)
    sales_starts_at: datetime | None = None
    sales_ends_at: datetime | None = None
    show_when_sold_out: bool | None = None
    button_text: str | None = Field(default=None, max_length=120)
    image_desktop_url: str | None = None
    image_mobile_url: str | None = None
    badge_text: str | None = Field(default=None, max_length=80)
    highlighted: bool | None = None
    config: dict[str, Any] | None = None

    @field_validator("config")
    @classmethod
    def validate_config(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _validated_offer_config(value)


class StrategicOfferDuplicate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=80)
    title: str | None = Field(default=None, min_length=1, max_length=200)


class StrategicOfferReorder(BaseModel):
    offer_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_offer_ids(self):
        if len(self.offer_ids) != len(set(self.offer_ids)):
            raise ValueError("A ordenação não pode conter ofertas repetidas.")
        return self


class StrategicOfferOut(BaseModel):
    id: str
    campaign_id: str
    code: str
    title: str
    description: str | None
    product_id: str | None
    kit_id: str | None
    reference_type: str = "product"
    components: list[StrategicOfferComponentIn] = Field(default_factory=list)
    selection_quantity: int | None = None
    pricing_strategy: str = "catalog"
    discount_percent: Decimal | None = None
    discount_amount: Decimal | None = None
    fixed_promotional_price: Decimal | None = None
    composition_revision: int = 1
    price_original: Decimal
    price_promotional: Decimal
    active: bool
    display_order: int
    quantity_limit: int | None
    max_per_customer: int | None
    sales_starts_at: datetime | None
    sales_ends_at: datetime | None
    show_when_sold_out: bool
    button_text: str | None
    image_desktop_url: str | None
    image_mobile_url: str | None
    badge_text: str | None
    highlighted: bool
    config: dict[str, Any]
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class StrategicCampaignOut(BaseModel):
    id: str
    name: str
    commercial_name: str | None
    slug: str
    description: str | None
    status: StrategicCampaignStatus
    starts_at: datetime | None
    ends_at: datetime | None
    visual_config: dict[str, Any]
    commercial_config: StrategicCommercialConfig = Field(default_factory=StrategicCommercialConfig)
    marketing_config: StrategicMarketingConfig = Field(default_factory=StrategicMarketingConfig)
    published_version: int | None
    offers: list[StrategicOfferOut] = []

    model_config = {"from_attributes": True}


class StrategicCampaignVersionOut(BaseModel):
    id: str
    campaign_id: str
    version: int
    snapshot: dict[str, Any]
    published_at: datetime

    model_config = {"from_attributes": True}


class StrategicCampaignSnapshotCampaign(BaseModel):
    id: str
    name: str
    commercial_name: str | None = None
    slug: str
    description: str | None = None
    status: StrategicCampaignStatus = StrategicCampaignStatus.active
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    visual_config: dict[str, Any] = Field(default_factory=dict)
    commercial_config: StrategicCommercialConfig = Field(default_factory=StrategicCommercialConfig)
    marketing_config: StrategicMarketingConfig = Field(default_factory=StrategicMarketingConfig)
    published_version: int = Field(ge=1)


class StrategicCampaignSnapshotOffer(BaseModel):
    id: str
    campaign_id: str
    code: str
    title: str
    description: str | None = None
    product_id: str | None = None
    kit_id: str | None = None
    reference_type: str = "product"
    components: list[StrategicOfferComponentIn] = Field(default_factory=list)
    pricing_strategy: str = "catalog"
    discount_percent: Decimal | None = None
    discount_amount: Decimal | None = None
    fixed_promotional_price: Decimal | None = None
    composition_revision: int = 1
    price_original: Decimal
    price_promotional: Decimal
    active: bool = True
    display_order: int = 0
    quantity_limit: int | None = None
    max_per_customer: int | None = None
    sales_starts_at: datetime | None = None
    sales_ends_at: datetime | None = None
    show_when_sold_out: bool = True
    available: bool | None = None
    remaining_quantity: int | None = None
    button_text: str | None = None
    image_desktop_url: str | None = None
    image_mobile_url: str | None = None
    badge_text: str | None = None
    highlighted: bool = False
    config: dict[str, Any] = Field(default_factory=dict)
    archived_at: datetime | None = None


class StrategicCampaignSnapshot(BaseModel):
    schema_version: Literal[STRATEGIC_CAMPAIGN_SNAPSHOT_SCHEMA_VERSION] = STRATEGIC_CAMPAIGN_SNAPSHOT_SCHEMA_VERSION
    campaign: StrategicCampaignSnapshotCampaign
    offers: list[StrategicCampaignSnapshotOffer] = Field(default_factory=list)

    def as_public_campaign(self) -> "StrategicCampaignPublicOut":
        return StrategicCampaignPublicOut(
            schema_version=self.schema_version,
            **self.campaign.model_dump(),
            offers=self.offers,
        )


class StrategicCampaignPublicOut(StrategicCampaignSnapshotCampaign):
    schema_version: int = STRATEGIC_CAMPAIGN_SNAPSHOT_SCHEMA_VERSION
    offers: list[StrategicCampaignSnapshotOffer] = Field(default_factory=list)


class StrategicAvailableCampaignOut(BaseModel):
    id: str
    name: str
    commercial_name: str
    slug: str
    published_version: int
    offers_available: int


class StrategicOfferConfigurationOut(BaseModel):
    offer_id: str
    campaign_id: str
    campaign_version: int
    composition_revision: int
    reference_type: str
    pricing_strategy: str
    price_range: dict[str, Decimal | None]
    steps: list[dict[str, Any]]
