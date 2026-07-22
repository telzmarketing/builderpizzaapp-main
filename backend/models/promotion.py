from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index, Text
from datetime import datetime, timezone
from backend.database import Base


class Promotion(Base):
    __tablename__ = "promotions"
    __table_args__ = (Index("uq_promotions_tenant_id_id", "tenant_id", "id", unique=True),)

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_promotions_tenant_id_tenants"), nullable=True)
    title = Column(String(200), nullable=False)
    subtitle = Column(String(300))
    description = Column(Text)
    icon = Column(Text, default="🍕")
    validity_text = Column(String(200), nullable=True)
    active = Column(Boolean, default=False)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
