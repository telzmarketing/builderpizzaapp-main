"""Received fiscal documents for inventory reconciliation.

These records are evidence of an inbound document only.  They do not create
stock movements, accounts payable, or a fiscal authorization by themselves.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, JSON, LargeBinary, Numeric, String, Text, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class InventoryReceiptDocument(Base):
    __tablename__ = "inventory_receipt_documents"
    __table_args__ = (
        Index("uq_inventory_receipt_documents_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_inventory_receipt_documents_tenant_hash", "tenant_id", "content_sha256", unique=True),
        Index(
            "uq_inventory_receipt_documents_tenant_access_key",
            "tenant_id", "access_key", unique=True,
            postgresql_where=text("access_key IS NOT NULL"),
        ),
        Index("uq_inventory_receipt_documents_tenant_idempotency", "tenant_id", "idempotency_key", unique=True),
        Index("ix_inventory_receipt_documents_tenant_status", "tenant_id", "status"),
        ForeignKeyConstraint(
            ["tenant_id", "purchase_id"],
            ["inventory_purchases.tenant_id", "inventory_purchases.id"],
            name="fk_inventory_receipt_document_purchase",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "supplier_id"],
            ["inventory_suppliers.tenant_id", "inventory_suppliers.id"],
            name="fk_inventory_receipt_document_supplier",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('uploaded','processing','review_required','validated','rejected')",
            name="ck_inventory_receipt_document_status",
        ),
        CheckConstraint("length(content_sha256) = 64", name="ck_inventory_receipt_document_hash"),
        CheckConstraint("document_model IN ('NFe','NFCe')", name="ck_inventory_receipt_document_model"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    purchase_id = Column(String, nullable=True, index=True)
    supplier_id = Column(String, nullable=True, index=True)
    document_model = Column(String(10), nullable=False, default="NFe", server_default="NFe")
    status = Column(String(30), nullable=False, default="uploaded", server_default="uploaded")
    access_key = Column(String(44), nullable=True)
    series = Column(String(10), nullable=True)
    number = Column(String(20), nullable=True)
    issuer_document = Column(String(20), nullable=True)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True)
    content_sha256 = Column(String(64), nullable=False)
    idempotency_key = Column(String(200), nullable=True)
    parser_version = Column(String(40), nullable=False, default="stdlib-xml-v1", server_default="stdlib-xml-v1")
    raw_xml = Column(Text, nullable=True)
    raw_content = Column(LargeBinary, nullable=True)
    source_filename = Column(String(255), nullable=True)
    source_mime_type = Column(String(120), nullable=True)
    extraction_method = Column(String(40), nullable=False, default="xml", server_default="xml")
    extraction_error = Column(String(500), nullable=True)
    extracted_json = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict, server_default="{}")
    validation_errors_json = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list, server_default="[]")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    purchase = relationship("InventoryPurchase")
    supplier = relationship("InventorySupplier")
    lines = relationship("InventoryReceiptDocumentLine", cascade="all, delete-orphan", back_populates="document")


class InventoryReceiptDocumentLine(Base):
    __tablename__ = "inventory_receipt_document_lines"
    __table_args__ = (
        Index("uq_inventory_receipt_document_lines_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_inventory_receipt_document_lines_document_line", "tenant_id", "document_id", "line_number", unique=True),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["inventory_receipt_documents.tenant_id", "inventory_receipt_documents.id"],
            name="fk_inventory_receipt_document_line_document",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "inventory_item_id"],
            ["inventory_items.tenant_id", "inventory_items.id"],
            name="fk_inventory_receipt_document_line_item",
            ondelete="SET NULL",
        ),
        CheckConstraint("line_number > 0", name="ck_inventory_receipt_document_line_number"),
        CheckConstraint("quantity > 0 AND CAST(quantity AS VARCHAR) <> 'NaN'", name="ck_inventory_receipt_document_line_quantity"),
        CheckConstraint("association_status IN ('pending','matched','ignored')", name="ck_inventory_receipt_document_line_association"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    document_id = Column(String, nullable=False, index=True)
    line_number = Column(Integer, nullable=False)
    supplier_code = Column(String(80), nullable=True)
    gtin = Column(String(20), nullable=True)
    description = Column(String(220), nullable=False)
    quantity = Column(Numeric(20, 6), nullable=False)
    commercial_unit = Column(String(20), nullable=True)
    unit_price = Column(Numeric(20, 8), nullable=True)
    total_price = Column(Numeric(20, 8), nullable=True)
    inventory_item_id = Column(String, nullable=True, index=True)
    association_status = Column(String(30), nullable=False, default="pending", server_default="pending")
    extracted_json = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    document = relationship("InventoryReceiptDocument", back_populates="lines")
    inventory_item = relationship("InventoryItem")
