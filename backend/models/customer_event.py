from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.database import Base


class CustomerEvent(Base):
    __tablename__ = "customer_events"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    session_id = Column(String(200), nullable=True)
    event_type = Column(String(80), nullable=False)
    event_name = Column(String(200), nullable=True)
    event_description = Column(Text, nullable=True)
    entity_type = Column(String(80), nullable=True)
    entity_id = Column(String, nullable=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    order_id = Column(String, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    campaign_id = Column(String, nullable=True)
    coupon_id = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)
    source = Column(String(100), nullable=True)
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    utm_campaign = Column(String(200), nullable=True)
    device_type = Column(String(30), nullable=True)
    browser = Column(String(80), nullable=True)
    operating_system = Column(String(80), nullable=True)
    ip_address = Column(String(50), nullable=True)
    page_url = Column(Text, nullable=True)
    referrer_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    customer = relationship("Customer", foreign_keys=[customer_id])
    product = relationship("Product", foreign_keys=[product_id])
    order = relationship("Order", foreign_keys=[order_id])
