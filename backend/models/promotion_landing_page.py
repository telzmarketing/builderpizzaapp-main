from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.database import Base


class PromotionLandingPage(Base):
    __tablename__ = "promotion_landing_pages"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_promotion_landing_pages_slug"),
    )

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    promotion_id = Column(String, ForeignKey("product_promotions.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(220), nullable=False)
    subtitle = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    cta_text = Column(String(80), nullable=False, default="Quero essa pizza")
    image_url = Column(Text, nullable=True)
    image_position = Column(String(40), nullable=False, default="center")
    content_alignment = Column(String(20), nullable=False, default="center")
    overlay_style = Column(String(40), nullable=False, default="dark-gradient")
    badge_text = Column(String(80), nullable=True)
    slug = Column(String(160), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="draft")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    published_at = Column(DateTime(timezone=True), nullable=True)

    product = relationship("Product")
    promotion = relationship("ProductPromotion")
