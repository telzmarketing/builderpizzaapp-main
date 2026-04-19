from sqlalchemy import Column, String, Float, Boolean, Integer, Enum, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from backend.database import Base


class PricingRule(str, enum.Enum):
    most_expensive = "most_expensive"
    average = "average"
    proportional = "proportional"


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    price = Column(Float, nullable=False)
    icon = Column(Text, default="🍕")
    rating = Column(Float, default=4.5)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    order_item_flavors = relationship("OrderItemFlavor", back_populates="product")


class MultiFlavorsConfig(Base):
    """Singleton-style table — only one row active at a time (id='default')."""
    __tablename__ = "multi_flavors_config"

    id = Column(String, primary_key=True, default="default")
    max_flavors = Column(Integer, default=2)          # 2 or 3
    pricing_rule = Column(
        Enum(PricingRule), default=PricingRule.most_expensive
    )
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
