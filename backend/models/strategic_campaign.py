from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Enum, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
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
        UniqueConstraint("tenant_id", "id", name="uq_strategic_campaigns_tenant_id"),
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
        UniqueConstraint("tenant_id", "id", name="uq_strategic_offers_tenant_id"),
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
    archived_at = Column(DateTime(timezone=True), nullable=True)
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


class StrategicCapacitySlot(Base):
    __tablename__ = "strategic_capacity_slots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "campaign_id"],
            ["strategic_campaigns.tenant_id", "strategic_campaigns.id"],
            name="fk_strategic_capacity_slots_campaign",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "offer_id"],
            ["strategic_offers.tenant_id", "strategic_offers.id"],
            name="fk_strategic_capacity_slots_offer",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id", "campaign_id", "offer_scope", "starts_at",
            name="uq_strategic_capacity_slot_scope_start",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_strategic_capacity_slots_tenant_id"),
        CheckConstraint("ends_at > starts_at", name="ck_strategic_capacity_slot_period"),
        CheckConstraint(
            "offer_scope = COALESCE(offer_id, '*')",
            name="ck_strategic_capacity_slot_offer_scope",
        ),
        CheckConstraint("capacity_total > 0", name="ck_strategic_capacity_slot_total"),
        CheckConstraint(
            "capacity_used >= 0 AND capacity_used <= capacity_total",
            name="ck_strategic_capacity_slot_usage",
        ),
        Index(
            "ix_strategic_capacity_slots_tenant_campaign_start",
            "tenant_id", "campaign_id", "starts_at",
        ),
        Index(
            "ix_strategic_capacity_slots_tenant_offer_start",
            "tenant_id", "offer_id", "starts_at",
        ),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    campaign_id = Column(String, nullable=False)
    offer_id = Column(String, nullable=True)
    # PostgreSQL treats NULLs as distinct in UNIQUE constraints. This stable
    # scope preserves uniqueness for campaign-wide slots as well as offer slots.
    offer_scope = Column(String, nullable=False, default="*")
    label = Column(String(160), nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    capacity_total = Column(Integer, nullable=False)
    capacity_used = Column(Integer, nullable=False, default=0)
    blocked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class StrategicReservation(Base):
    __tablename__ = "strategic_reservations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "slot_id"],
            ["strategic_capacity_slots.tenant_id", "strategic_capacity_slots.id"],
            name="fk_strategic_reservations_slot",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "campaign_id"],
            ["strategic_campaigns.tenant_id", "strategic_campaigns.id"],
            name="fk_strategic_reservations_campaign",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "offer_id"],
            ["strategic_offers.tenant_id", "strategic_offers.id"],
            name="fk_strategic_reservations_offer",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            name="fk_strategic_reservations_order",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id", "idempotency_key",
            name="uq_strategic_reservations_tenant_idempotency",
        ),
        UniqueConstraint(
            "tenant_id", "order_id",
            name="uq_strategic_reservations_tenant_order",
        ),
        CheckConstraint("quantity > 0", name="ck_strategic_reservation_quantity"),
        CheckConstraint(
            "status IN ('held','confirmed','released','expired','cancelled')",
            name="ck_strategic_reservation_status",
        ),
        CheckConstraint(
            "payment_mode IN ('no_payment','partial','full')",
            name="ck_strategic_reservation_payment_mode",
        ),
        CheckConstraint(
            "amount_total >= 0 AND amount_paid >= 0 AND amount_paid <= amount_total",
            name="ck_strategic_reservation_amounts",
        ),
        Index(
            "ix_strategic_reservations_tenant_campaign_status",
            "tenant_id", "campaign_id", "status", "created_at",
        ),
        Index(
            "ix_strategic_reservations_tenant_slot_status_expiry",
            "tenant_id", "slot_id", "status", "expires_at",
        ),
        Index(
            "ix_strategic_reservations_tenant_operational_release",
            "tenant_id", "status", "operational_released_at",
        ),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    campaign_id = Column(String, nullable=False)
    offer_id = Column(String, nullable=True)
    slot_id = Column(String, nullable=False)
    order_id = Column(String, nullable=True)
    customer_reference = Column(String(200), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="held")
    payment_mode = Column(String(20), nullable=False, default="no_payment")
    amount_total = Column(Numeric(20, 2), nullable=False, default=0)
    amount_paid = Column(Numeric(20, 2), nullable=False, default=0)
    idempotency_key = Column(String(200), nullable=False)
    request_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    released_at = Column(DateTime(timezone=True), nullable=True)
    release_reason = Column(String(300), nullable=True)
    operational_released_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
