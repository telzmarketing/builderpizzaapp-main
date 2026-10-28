from sqlalchemy import Column, String, Float, Boolean, Integer, Enum, Text, DateTime, ForeignKey, JSON, Index, UniqueConstraint, CheckConstraint, ForeignKeyConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from backend.database import Base


class PricingRule(str, enum.Enum):
    most_expensive = "most_expensive"
    average = "average"
    proportional = "proportional"


class ProductType(str, enum.Enum):
    pizza = "pizza"
    drink = "drink"
    other = "other"


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (Index("uq_products_tenant_id_id", "tenant_id", "id", unique=True),)

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_products_tenant_id_tenants"), nullable=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    price = Column(Float, nullable=False)
    icon = Column(Text, default="🍕")
    category = Column(String(100), nullable=True)
    subcategory = Column(String(100), nullable=True)
    category_id = Column(String, ForeignKey("product_categories.id", ondelete="SET NULL"), nullable=True)
    subcategory_id = Column(String, ForeignKey("product_categories.id", ondelete="SET NULL"), nullable=True)
    product_type = Column(String(20), nullable=True)  # "pizza" | "drink" | "other"
    visible_delivery = Column(Boolean, nullable=False, default=True)
    visible_dine_in = Column(Boolean, nullable=False, default=True)
    show_crust_options = Column(Boolean, nullable=False, default=True, server_default="true")
    delivery_price = Column(Float, nullable=True)
    dine_in_price = Column(Float, nullable=True)
    rating = Column(Float, default=4.5)
    active = Column(Boolean, default=True)
    best_seller_badge_mode = Column(String(10), default="off")  # "off" | "manual" | "auto"
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    order_item_flavors = relationship("OrderItemFlavor", back_populates="product")
    sizes = relationship("ProductSize", back_populates="product", cascade="all, delete-orphan", order_by="ProductSize.sort_order")
    crust_types = relationship("ProductCrustType", back_populates="product", cascade="all, delete-orphan", order_by="ProductCrustType.sort_order")
    drink_variants = relationship("ProductDrinkVariant", back_populates="product", cascade="all, delete-orphan", order_by="ProductDrinkVariant.sort_order")
    option_groups = relationship("ProductOptionGroup", back_populates="product", cascade="all, delete-orphan", order_by="ProductOptionGroup.sort_order")
    promotions = relationship("ProductPromotion", foreign_keys="ProductPromotion.product_id", back_populates="product", cascade="all, delete-orphan")


class ProductCategory(Base):
    __tablename__ = "product_categories"
    __table_args__ = (Index("uq_product_categories_tenant_id_id", "tenant_id", "id", unique=True), UniqueConstraint("tenant_id", "name", name="uq_product_categories_tenant_name"))

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_product_categories_tenant_id_tenants"), nullable=True)
    parent_id = Column(String, ForeignKey("product_categories.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(100), nullable=False)
    active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    enable_sizes = Column(Boolean, nullable=False, default=False, server_default="false")
    enable_product_options = Column(Boolean, nullable=False, default=False, server_default="false")
    enable_recipe = Column(Boolean, nullable=False, default=False, server_default="false")
    enable_dough = Column(Boolean, nullable=False, default=False, server_default="false")
    enable_border = Column(Boolean, nullable=False, default=False, server_default="false")
    enable_promotions = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class ProductSize(Base):
    __tablename__ = "product_sizes"
    __table_args__ = (Index("uq_product_sizes_tenant_id_id", "tenant_id", "id", unique=True),)

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_product_sizes_tenant_id_tenants"), nullable=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    label = Column(String(50), nullable=False)
    description = Column(String(200), nullable=True)
    price = Column(Float, nullable=False)
    is_default = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="sizes")


class ProductCrustType(Base):
    """Available crust types for a pizza product."""
    __tablename__ = "product_crust_types"
    __table_args__ = (Index("uq_product_crust_types_tenant_id_id", "tenant_id", "id", unique=True),)

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_product_crust_types_tenant_id_tenants"), nullable=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    price_addition = Column(Float, default=0.0)
    active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="crust_types")


class ProductDrinkVariant(Base):
    """Drink type variants (e.g., Normal, Zero) for a drink product."""
    __tablename__ = "product_drink_variants"
    __table_args__ = (Index("uq_product_drink_variants_tenant_id_id", "tenant_id", "id", unique=True),)

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_product_drink_variants_tenant_id_tenants"), nullable=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    price_addition = Column(Float, default=0.0)
    active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="drink_variants")


class ProductOptionGroup(Base):
    """Configurable customer-facing option group owned by one product."""
    __tablename__ = "product_option_groups"
    __table_args__ = (
        Index("uq_product_option_groups_tenant_id_id", "tenant_id", "id", unique=True),
        UniqueConstraint("tenant_id", "product_id", "key", name="uq_product_option_groups_product_key"),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_product_option_groups_tenant_product",
            ondelete="CASCADE",
        ),
        CheckConstraint("selection_type IN ('single','multiple','quantity','text')", name="ck_product_option_groups_selection_type"),
        CheckConstraint("sort_order >= 0", name="ck_product_option_groups_sort_order"),
        CheckConstraint("min_selections >= 0 AND max_selections >= min_selections", name="ck_product_option_groups_selection_bounds"),
        CheckConstraint("NOT required OR min_selections >= 1", name="ck_product_option_groups_required_minimum"),
        CheckConstraint("selection_type <> 'single' OR max_selections <= 1", name="ck_product_option_groups_single_maximum"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_product_option_groups_tenant_id_tenants"), nullable=True)
    product_id = Column(String, nullable=False)
    key = Column(String(64), nullable=False)
    name = Column(String(100), nullable=False)
    selection_type = Column(String(16), nullable=False, default="single", server_default="single")
    required = Column(Boolean, nullable=False, default=False, server_default="false")
    min_selections = Column(Integer, nullable=False, default=0, server_default="0")
    max_selections = Column(Integer, nullable=False, default=1, server_default="1")
    sort_order = Column(Integer, nullable=False, default=0, server_default="0")
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="option_groups")
    options = relationship("ProductOption", back_populates="group", cascade="all, delete-orphan", order_by="ProductOption.sort_order")


class ProductOption(Base):
    """Selectable value inside a product option group."""
    __tablename__ = "product_options"
    __table_args__ = (
        Index("uq_product_options_tenant_id_id", "tenant_id", "id", unique=True),
        UniqueConstraint("tenant_id", "group_id", "key", name="uq_product_options_group_key"),
        ForeignKeyConstraint(
            ["tenant_id", "group_id"],
            ["product_option_groups.tenant_id", "product_option_groups.id"],
            name="fk_product_options_tenant_group",
            ondelete="CASCADE",
        ),
        CheckConstraint("sort_order >= 0", name="ck_product_options_sort_order"),
        CheckConstraint("price_addition >= 0", name="ck_product_options_price_addition"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_product_options_tenant_id_tenants"), nullable=True)
    group_id = Column(String, nullable=False)
    key = Column(String(64), nullable=False)
    name = Column(String(120), nullable=False)
    price_addition = Column(Float, nullable=False, default=0.0, server_default="0")
    sort_order = Column(Integer, nullable=False, default=0, server_default="0")
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    group = relationship("ProductOptionGroup", back_populates="options")


class BestSellerConfig(Base):
    """Singleton config for automatic best-seller badge calculation."""
    __tablename__ = "best_seller_config"
    __table_args__ = (Index("uq_best_seller_config_tenant_id_id", "tenant_id", "id", unique=True),)

    id = Column(String, primary_key=True, default="default")
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_best_seller_config_tenant_id_tenants"), nullable=True)
    period_days = Column(Integer, default=30)  # 0 = all time
    top_count = Column(Integer, default=5)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class MultiFlavorsConfig(Base):
    """Singleton-style table — only one row active at a time (id='default')."""
    __tablename__ = "multi_flavors_config"
    __table_args__ = (Index("uq_multi_flavors_config_tenant_id_id", "tenant_id", "id", unique=True),)

    id = Column(String, primary_key=True, default="default")
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_multi_flavors_config_tenant_id_tenants"), nullable=True)
    max_flavors = Column(Integer, default=2)
    pricing_rule = Column(
        Enum(PricingRule), default=PricingRule.most_expensive
    )
    flavor_category_filters = Column(JSON, default=list)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
