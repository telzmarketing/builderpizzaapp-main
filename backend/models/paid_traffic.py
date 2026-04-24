from datetime import date, datetime, timezone
import enum

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.database import Base


class TrafficPlatform(str, enum.Enum):
    meta = "meta"
    google = "google"
    tiktok = "tiktok"
    manual = "manual"


class TrafficCampaignStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    ended = "ended"


class AdIntegrationStatus(str, enum.Enum):
    disconnected = "disconnected"
    connected = "connected"
    error = "error"


class TrafficCampaign(Base):
    __tablename__ = "traffic_campaigns"

    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    platform = Column(String(30), nullable=False, default=TrafficPlatform.manual.value)
    status = Column(String(30), nullable=False, default=TrafficCampaignStatus.draft.value)
    daily_budget = Column(Float, nullable=True)
    total_budget = Column(Float, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    coupon_id = Column(String, ForeignKey("coupons.id", ondelete="SET NULL"), nullable=True)
    destination_url = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    links = relationship("CampaignLink", back_populates="campaign", cascade="all, delete-orphan")
    product = relationship("Product", foreign_keys=[product_id])
    coupon = relationship("Coupon", foreign_keys=[coupon_id])

    __table_args__ = (
        Index("ix_traffic_campaigns_platform_status", "platform", "status"),
        Index("ix_traffic_campaigns_product_id", "product_id"),
    )


class CampaignLink(Base):
    __tablename__ = "campaign_links"

    id = Column(String, primary_key=True)
    campaign_id = Column(String, ForeignKey("traffic_campaigns.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=True)
    destination_url = Column(Text, nullable=False)
    final_url = Column(Text, nullable=False)
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    utm_campaign = Column(String(200), nullable=True)
    utm_content = Column(String(200), nullable=True)
    utm_term = Column(String(200), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    campaign = relationship("TrafficCampaign", back_populates="links")

    __table_args__ = (
        Index("ix_campaign_links_campaign_id", "campaign_id"),
        Index("ix_campaign_links_utm_campaign", "utm_campaign"),
    )


class TrackingSession(Base):
    __tablename__ = "tracking_sessions"

    id = Column(String, primary_key=True)
    campaign_id = Column(String, ForeignKey("traffic_campaigns.id", ondelete="SET NULL"), nullable=True)
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    utm_campaign = Column(String(200), nullable=True)
    utm_content = Column(String(200), nullable=True)
    utm_term = Column(String(200), nullable=True)
    landing_page = Column(Text, nullable=True)
    referrer = Column(Text, nullable=True)
    first_seen_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_tracking_sessions_campaign_id", "campaign_id"),
        Index("ix_tracking_sessions_utm_campaign", "utm_campaign"),
    )


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("tracking_sessions.id", ondelete="SET NULL"), nullable=True)
    campaign_id = Column(String, ForeignKey("traffic_campaigns.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(60), nullable=False)
    value = Column(Float, nullable=True)
    path = Column(Text, nullable=True)
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    utm_campaign = Column(String(200), nullable=True)
    utm_content = Column(String(200), nullable=True)
    utm_term = Column(String(200), nullable=True)
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_tracking_events_session_id", "session_id"),
        Index("ix_tracking_events_campaign_id", "campaign_id"),
        Index("ix_tracking_events_type_created", "event_type", "created_at"),
    )


class AdPlatformIntegration(Base):
    __tablename__ = "ad_platform_integrations"

    id = Column(String, primary_key=True)
    platform = Column(String(30), nullable=False, unique=True)
    status = Column(String(30), nullable=False, default=AdIntegrationStatus.disconnected.value)
    access_token_encrypted = Column(Text, nullable=True)
    refresh_token_encrypted = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    account_name = Column(String(200), nullable=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AdAccount(Base):
    __tablename__ = "ad_accounts"

    id = Column(String, primary_key=True)
    integration_id = Column(String, ForeignKey("ad_platform_integrations.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(30), nullable=False)
    external_account_id = Column(String(200), nullable=False)
    name = Column(String(200), nullable=False)
    currency = Column(String(10), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AdCampaignExternal(Base):
    __tablename__ = "ad_campaigns_external"

    id = Column(String, primary_key=True)
    traffic_campaign_id = Column(String, ForeignKey("traffic_campaigns.id", ondelete="SET NULL"), nullable=True)
    ad_account_id = Column(String, ForeignKey("ad_accounts.id", ondelete="SET NULL"), nullable=True)
    platform = Column(String(30), nullable=False)
    external_campaign_id = Column(String(200), nullable=False)
    name = Column(String(300), nullable=False)
    status = Column(String(60), nullable=True)
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AdDailyMetric(Base):
    __tablename__ = "ad_daily_metrics"

    id = Column(String, primary_key=True)
    traffic_campaign_id = Column(String, ForeignKey("traffic_campaigns.id", ondelete="SET NULL"), nullable=True)
    platform = Column(String(30), nullable=False)
    metric_date = Column(Date, nullable=False)
    spend = Column(Float, default=0.0)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Float, default=0.0)
    cpc = Column(Float, default=0.0)
    ctr = Column(Float, default=0.0)
    roas = Column(Float, nullable=True)
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_ad_daily_metrics_campaign_date", "traffic_campaign_id", "metric_date"),
        Index("ix_ad_daily_metrics_platform_date", "platform", "metric_date"),
    )


class CampaignSettings(Base):
    __tablename__ = "campaign_settings"

    id = Column(String, primary_key=True, default="default")
    attribution_window_days = Column(Integer, default=7)
    attribution_model = Column(String(30), default="last_click")
    default_margin = Column(Float, default=0.3)
    target_roas = Column(Float, default=2.0)
    tracking_enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AdSyncLog(Base):
    __tablename__ = "ad_sync_logs"

    id = Column(String, primary_key=True)
    platform = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False)
    message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime(timezone=True), nullable=True)
