from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.database import Base


class ProductPromotion(Base):
    __tablename__ = "product_promotions"

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    valid_weekdays = Column(Text, nullable=False, default="[]")
    start_time = Column(String(5), nullable=True)
    end_time = Column(String(5), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    discount_type = Column(String(30), nullable=False, default="fixed_price")
    default_value = Column(Float, nullable=True)
    free_shipping = Column(Boolean, default=False, nullable=False)
    gift_enabled = Column(Boolean, default=False, nullable=False)
    gift_product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    gift_quantity = Column(Integer, default=1, nullable=False)
    blocks_other_coupons = Column(Boolean, default=False, nullable=False)
    timezone = Column(String(80), nullable=False, default="America/Sao_Paulo")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    product = relationship("Product", foreign_keys=[product_id], back_populates="promotions")
    gift_product = relationship("Product", foreign_keys=[gift_product_id])
    combinations = relationship(
        "ProductPromotionCombination",
        back_populates="promotion",
        cascade="all, delete-orphan",
        order_by="ProductPromotionCombination.created_at",
    )


class ProductPromotionCombination(Base):
    __tablename__ = "product_promotion_combinations"
    __table_args__ = (
        UniqueConstraint(
            "promotion_id",
            "product_size_id",
            "product_crust_type_id",
            name="uq_product_promotion_combination",
        ),
    )

    id = Column(String, primary_key=True)
    promotion_id = Column(String, ForeignKey("product_promotions.id", ondelete="CASCADE"), nullable=False, index=True)
    product_size_id = Column(String, ForeignKey("product_sizes.id", ondelete="CASCADE"), nullable=True, index=True)
    product_crust_type_id = Column(String, ForeignKey("product_crust_types.id", ondelete="CASCADE"), nullable=True, index=True)
    active = Column(Boolean, default=True, nullable=False)
    promotional_value = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    promotion = relationship("ProductPromotion", back_populates="combinations")
