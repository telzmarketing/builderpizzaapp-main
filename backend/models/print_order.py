"""Tenant-scoped persistence for the Print Pedido import channel."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


_JSON = JSON().with_variant(JSONB(), "postgresql")


class PrintOrderImport(Base):
    """One captured print/document and its review/confirmation lifecycle."""

    __tablename__ = "print_order_imports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('awaiting_review', 'ready', 'imported', 'duplicate', 'error', 'cancelled')",
            name="ck_print_order_imports_status",
        ),
        CheckConstraint(
            "platform IN ('ifood', '99food', 'keeta', 'unknown')",
            name="ck_print_order_imports_platform",
        ),
        Index("ix_print_order_imports_tenant_status", "tenant_id", "status"),
        Index("ix_print_order_imports_tenant_created", "tenant_id", "created_at"),
        Index(
            "uq_print_order_imports_dedupe_key",
            "dedupe_key",
            unique=True,
            postgresql_where=text("dedupe_key IS NOT NULL"),
        ),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    source_asset_id = Column(String(32), ForeignKey("tenant_upload_assets.id", ondelete="RESTRICT"), nullable=False)
    source_filename = Column(String(255), nullable=False)
    source_content_type = Column(String(120), nullable=False)
    platform = Column(String(20), nullable=False, default="unknown", server_default="unknown")
    store_identifier = Column(String(120), nullable=True)
    external_order_number = Column(String(120), nullable=True)
    # Only the first capture for a known external order owns this key. A later
    # capture is retained as a duplicate row without weakening the DB guard.
    dedupe_key = Column(String(300), nullable=True)
    status = Column(String(20), nullable=False, default="awaiting_review", server_default="awaiting_review")
    parser_version = Column(String(30), nullable=False, default="deterministic-v1", server_default="deterministic-v1")
    raw_text = Column(Text, nullable=True)
    normalized_payload = Column(_JSON, nullable=False, default=dict, server_default="{}")
    review_notes = Column(_JSON, nullable=False, default=list, server_default="[]")
    duplicate_of_id = Column(String(36), ForeignKey("print_order_imports.id", ondelete="SET NULL"), nullable=True)
    order_id = Column(String, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    created_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    confirmed_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class PrintOrderItem(Base):
    """A normalized/interpreted line, never a second order line."""

    __tablename__ = "print_order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_print_order_items_quantity"),
        CheckConstraint(
            "match_status IN ('unmatched', 'review', 'matched')",
            name="ck_print_order_items_match_status",
        ),
        Index("ix_print_order_items_tenant_import", "tenant_id", "import_id"),
        Index("ix_print_order_items_tenant_product", "tenant_id", "product_id"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    import_id = Column(String(36), ForeignKey("print_order_imports.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    external_product_id = Column(String(120), nullable=True)
    external_name = Column(String(300), nullable=False)
    normalized_name = Column(String(300), nullable=False)
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    selected_size = Column(String(80), nullable=True)
    flavor_names = Column(_JSON, nullable=False, default=list, server_default="[]")
    customizations = Column(_JSON, nullable=False, default=dict, server_default="{}")
    unit_price = Column(Numeric(20, 2), nullable=True)
    total_price = Column(Numeric(20, 2), nullable=True)
    match_status = Column(String(20), nullable=False, default="unmatched", server_default="unmatched")
    match_reason = Column(String(300), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class PrintOrderCatalogMapping(Base):
    """Approved tenant catalog alias for future imports."""

    __tablename__ = "print_order_catalog_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "platform",
            "normalized_external_name",
            name="uq_print_order_mapping_name",
        ),
        Index("ix_print_order_mappings_tenant_platform", "tenant_id", "platform"),
        Index(
            "uq_print_order_mapping_external_id",
            "tenant_id",
            "platform",
            "external_product_id",
            unique=True,
            postgresql_where=text("external_product_id IS NOT NULL"),
        ),
        CheckConstraint(
            "platform IN ('ifood', '99food', 'keeta', 'unknown')",
            name="ck_print_order_mappings_platform",
        ),
        CheckConstraint(
            "status IN ('approved', 'revoked')",
            name="ck_print_order_mappings_status",
        ),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    platform = Column(String(20), nullable=False)
    external_product_id = Column(String(120), nullable=True)
    external_name = Column(String(300), nullable=False)
    normalized_external_name = Column(String(300), nullable=False)
    product_id = Column(String, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    variation = Column(_JSON, nullable=False, default=dict, server_default="{}")
    status = Column(String(20), nullable=False, default="approved", server_default="approved")
    created_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
