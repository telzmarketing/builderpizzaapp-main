from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.database import Base


class StrategicCampaignStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    active = "active"
    paused = "paused"
    sold_out = "sold_out"
    ended = "ended"
    archived = "archived"


class StrategicCampaign(Base):
    __tablename__ = "strategic_campaigns"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_strategic_campaigns_tenant_slug"),
        Index("ix_strategic_campaigns_tenant_status", "tenant_id", "status"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(200), nullable=False)
    commercial_name = Column(String(200), nullable=True)
    slug = Column(String(180), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(StrategicCampaignStatus), nullable=False, default=StrategicCampaignStatus.draft)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    visual_config = Column(JSON, nullable=False, default=dict)
    commercial_config = Column(JSON, nullable=False, default=dict)
    marketing_config = Column(JSON, nullable=False, default=dict)
    published_version = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    offers = relationship("StrategicOffer", back_populates="campaign", cascade="all, delete-orphan")
    versions = relationship("StrategicCampaignVersion", back_populates="campaign", cascade="all, delete-orphan")


class StrategicOffer(Base):
    __tablename__ = "strategic_offers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "campaign_id", "code", name="uq_strategic_offers_tenant_campaign_code"),
        Index("ix_strategic_offers_tenant_campaign", "tenant_id", "campaign_id"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    campaign_id = Column(String, ForeignKey("strategic_campaigns.id", ondelete="RESTRICT"), nullable=False)
    code = Column(String(80), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="RESTRICT"), nullable=True)
    kit_id = Column(String, ForeignKey("promotional_kits.id", ondelete="RESTRICT"), nullable=True)
    price_original = Column(Numeric(20, 2), nullable=False, default=0)
    price_promotional = Column(Numeric(20, 2), nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)
    display_order = Column(Integer, nullable=False, default=0)
    quantity_limit = Column(Integer, nullable=True)
    max_per_customer = Column(Integer, nullable=True)
    sales_starts_at = Column(DateTime(timezone=True), nullable=True)
    sales_ends_at = Column(DateTime(timezone=True), nullable=True)
    show_when_sold_out = Column(Boolean, nullable=False, default=True)
    button_text = Column(String(120), nullable=True)
    image_desktop_url = Column(Text, nullable=True)
    image_mobile_url = Column(Text, nullable=True)
    badge_text = Column(String(80), nullable=True)
    highlighted = Column(Boolean, nullable=False, default=False)
    config = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    campaign = relationship("StrategicCampaign", back_populates="offers")


class StrategicCampaignVersion(Base):
    __tablename__ = "strategic_campaign_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "campaign_id", "version", name="uq_strategic_campaign_versions_number"),
        Index("ix_strategic_campaign_versions_tenant_campaign", "tenant_id", "campaign_id"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    campaign_id = Column(String, ForeignKey("strategic_campaigns.id", ondelete="RESTRICT"), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    campaign = relationship("StrategicCampaign", back_populates="versions")
