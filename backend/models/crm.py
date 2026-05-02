from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint

from backend.database import Base


class CustomerTag(Base):
    __tablename__ = "customer_tags"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_customer_tags_tenant_slug"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String(100), nullable=False, default="default")
    name = Column(String(120), nullable=False)
    slug = Column(String(140), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(20), nullable=False, default="#f97316")
    status = Column(String(20), nullable=False, default="active")
    source = Column(String(40), nullable=False, default="manual")
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CustomerTagAssignment(Base):
    __tablename__ = "customer_tag_assignments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "customer_id", "tag_id", name="uq_customer_tag_assignment"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String(100), nullable=False, default="default")
    customer_id = Column(String, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    tag_id = Column(String, ForeignKey("customer_tags.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(40), nullable=False, default="manual")
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CustomerSegment(Base):
    __tablename__ = "customer_segments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_customer_segments_tenant_slug"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String(100), nullable=False, default="default")
    name = Column(String(160), nullable=False)
    slug = Column(String(180), nullable=False)
    description = Column(Text, nullable=True)
    rules_json = Column(Text, nullable=False, default="[]")
    status = Column(String(20), nullable=False, default="active")
    source = Column(String(40), nullable=False, default="manual")
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
