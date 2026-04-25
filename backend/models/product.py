from sqlalchemy import Column, String, Float, Boolean, Integer, Enum, Text, DateTime, ForeignKey
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

    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    price = Column(Float, nullable=False)
    icon = Column(Text, default="🍕")
    category = Column(String(100), nullable=True)
    product_type = Column(String(20), nullable=True)  # "pizza" | "drink" | "other"
    rating = Column(Float, default=4.5)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    order_item_flavors = relationship("OrderItemFlavor", back_populates="product")
    sizes = relationship("ProductSize", back_populates="product", cascade="all, delete-orphan", order_by="ProductSize.sort_order")
    crust_types = relationship("ProductCrustType", back_populates="product", cascade="all, delete-orphan", order_by="ProductCrustType.sort_order")
    drink_variants = relationship("ProductDrinkVariant", back_populates="product", cascade="all, delete-orphan", order_by="ProductDrinkVariant.sort_order")
    promotions = relationship("ProductPromotion", back_populates="product", cascade="all, delete-orphan")


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id = Column(String, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class ProductSize(Base):
    __tablename__ = "product_sizes"

    id = Column(String, primary_key=True)
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

    id = Column(String, primary_key=True)
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

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    price_addition = Column(Float, default=0.0)
    active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="drink_variants")


class MultiFlavorsConfig(Base):
    """Singleton-style table — only one row active at a time (id='default')."""
    __tablename__ = "multi_flavors_config"

    id = Column(String, primary_key=True, default="default")
    max_flavors = Column(Integer, default=2)
    pricing_rule = Column(
        Enum(PricingRule), default=PricingRule.most_expensive
    )
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
