from sqlalchemy import Column, String, Float, Boolean, Integer, Enum, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from backend.database import Base


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    ended = "ended"


class CampaignType(str, enum.Enum):
    exclusive_page = "exclusive_page"
    products_promo = "products_promo"


class CpDiscountType(str, enum.Enum):
    percentage = "percentage"
    fixed = "fixed"


class KitType(str, enum.Enum):
    kit = "kit"
    product = "product"
    item = "item"


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(CampaignStatus), default=CampaignStatus.draft, nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=True)
    end_at = Column(DateTime(timezone=True), nullable=True)
    banner = Column(Text, nullable=True)
    slug = Column(String(200), unique=True, nullable=False)
    campaign_type = Column(Enum(CampaignType), nullable=False, default=CampaignType.products_promo)
    display_title = Column(String(300), nullable=True)
    display_subtitle = Column(String(300), nullable=True)
    display_order = Column(Integer, default=0)
    published = Column(Boolean, default=False)
    active_days = Column(String(20), nullable=True)  # "0,1,2,3,4,5,6" — NULL = all days
    card_bg_color = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    campaign_products = relationship("CampaignProduct", back_populates="campaign", cascade="all, delete-orphan")


class CampaignProduct(Base):
    __tablename__ = "campaign_products"

    id = Column(String, primary_key=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=True)
    kit_id = Column(String, ForeignKey("promotional_kits.id"), nullable=True)
    promotional_price = Column(Float, nullable=True)
    discount_type = Column(Enum(CpDiscountType), nullable=True)
    discount_value = Column(Float, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    campaign = relationship("Campaign", back_populates="campaign_products")
    product = relationship("Product", foreign_keys=[product_id])
    kit = relationship("PromotionalKit", foreign_keys=[kit_id])


class PromotionalKit(Base):
    __tablename__ = "promotional_kits"

    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(50), default="🎁")
    kit_type = Column(Enum(KitType), default=KitType.kit)
    price_original = Column(Float, default=0.0)
    price_promotional = Column(Float, default=0.0)
    discount_type = Column(Enum(CpDiscountType), nullable=True)
    discount_value = Column(Float, nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    items = relationship("PromotionalKitItem", back_populates="kit", cascade="all, delete-orphan")
    campaign_products = relationship("CampaignProduct", back_populates="kit")


class PromotionalKitItem(Base):
    __tablename__ = "promotional_kit_items"

    id = Column(String, primary_key=True)
    kit_id = Column(String, ForeignKey("promotional_kits.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1)

    kit = relationship("PromotionalKit", back_populates="items")
    product = relationship("Product", foreign_keys=[product_id])
