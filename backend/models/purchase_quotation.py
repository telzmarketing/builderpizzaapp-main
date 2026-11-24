"""Tenant-scoped purchase quotations and supplier offers."""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class PurchaseQuotation(Base):
    __tablename__ = "purchase_quotations"
    __table_args__ = (
        Index("uq_purchase_quotations_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_purchase_quotations_tenant_code", "tenant_id", "code", unique=True),
        Index("ix_purchase_quotations_tenant_status", "tenant_id", "status"),
        ForeignKeyConstraint(["tenant_id", "requisition_id"], ["purchase_requisitions.tenant_id", "purchase_requisitions.id"], name="fk_purchase_quotations_requisition", ondelete="RESTRICT"),
        CheckConstraint("status IN ('draft','open','closed','awarded','cancelled')", name="ck_purchase_quotations_status"),
        CheckConstraint("version > 0", name="ck_purchase_quotations_version"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    requisition_id = Column(String(36), nullable=False)
    code = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, default="draft", server_default="draft")
    response_due = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False)
    awarded_supplier_id = Column(String, ForeignKey("inventory_suppliers.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    requisition = relationship("PurchaseRequisition")
    suppliers = relationship("PurchaseQuotationSupplier", cascade="all, delete-orphan", back_populates="quotation")
    lines = relationship("PurchaseQuotationLine", cascade="all, delete-orphan", back_populates="quotation", order_by="PurchaseQuotationLine.position")
    offers = relationship("PurchaseQuotationOffer", cascade="all, delete-orphan", back_populates="quotation")


class PurchaseQuotationSupplier(Base):
    __tablename__ = "purchase_quotation_suppliers"
    __table_args__ = (
        Index("uq_purchase_quotation_suppliers_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_purchase_quotation_suppliers_tenant_quotation_supplier", "tenant_id", "quotation_id", "supplier_id", unique=True),
        ForeignKeyConstraint(["tenant_id", "quotation_id"], ["purchase_quotations.tenant_id", "purchase_quotations.id"], name="fk_purchase_quotation_suppliers_quotation", ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "supplier_id"], ["inventory_suppliers.tenant_id", "inventory_suppliers.id"], name="fk_purchase_quotation_suppliers_supplier", ondelete="RESTRICT"),
        CheckConstraint("status IN ('invited','responded','declined')", name="ck_purchase_quotation_suppliers_status"),
    )
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    quotation_id = Column(String(36), nullable=False)
    supplier_id = Column(String, nullable=False)
    status = Column(String(20), nullable=False, default="invited", server_default="invited")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    quotation = relationship("PurchaseQuotation", back_populates="suppliers")
    supplier = relationship("InventorySupplier", overlaps="quotation,suppliers")


class PurchaseQuotationLine(Base):
    __tablename__ = "purchase_quotation_lines"
    __table_args__ = (
        Index("uq_purchase_quotation_lines_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_purchase_quotation_lines_position", "tenant_id", "quotation_id", "position", unique=True),
        ForeignKeyConstraint(["tenant_id", "quotation_id"], ["purchase_quotations.tenant_id", "purchase_quotations.id"], name="fk_purchase_quotation_lines_quotation", ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "item_id"], ["inventory_items.tenant_id", "inventory_items.id"], name="fk_purchase_quotation_lines_item", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "unit_id"], ["inventory_units.tenant_id", "inventory_units.id"], name="fk_purchase_quotation_lines_unit", ondelete="RESTRICT"),
        CheckConstraint("quantity > 0", name="ck_purchase_quotation_lines_quantity"),
        CheckConstraint("position >= 0", name="ck_purchase_quotation_lines_position"),
    )
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    quotation_id = Column(String(36), nullable=False)
    item_id = Column(String, nullable=False)
    unit_id = Column(String, nullable=False)
    quantity = Column(Numeric(20, 6), nullable=False)
    position = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    quotation = relationship("PurchaseQuotation", back_populates="lines")
    item = relationship("InventoryItem", overlaps="lines,quotation")
    unit = relationship("InventoryUnit", overlaps="item,lines,quotation")


class PurchaseQuotationOffer(Base):
    __tablename__ = "purchase_quotation_offers"
    __table_args__ = (
        Index("uq_purchase_quotation_offers_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_purchase_quotation_offers_line_supplier", "tenant_id", "quotation_line_id", "supplier_id", unique=True),
        ForeignKeyConstraint(["tenant_id", "quotation_id"], ["purchase_quotations.tenant_id", "purchase_quotations.id"], name="fk_purchase_quotation_offers_quotation", ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "quotation_line_id"], ["purchase_quotation_lines.tenant_id", "purchase_quotation_lines.id"], name="fk_purchase_quotation_offers_line", ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "supplier_id"], ["inventory_suppliers.tenant_id", "inventory_suppliers.id"], name="fk_purchase_quotation_offers_supplier", ondelete="RESTRICT"),
        CheckConstraint("unit_price >= 0 AND freight >= 0 AND discount >= 0", name="ck_purchase_quotation_offers_nonnegative"),
        CheckConstraint("conversion_factor > 0", name="ck_purchase_quotation_offers_conversion"),
    )
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    quotation_id = Column(String(36), nullable=False)
    quotation_line_id = Column(String(36), nullable=False)
    supplier_id = Column(String, nullable=False)
    unit_price = Column(Numeric(20, 8), nullable=False)
    conversion_factor = Column(Numeric(20, 8), nullable=False, default=1, server_default="1")
    freight = Column(Numeric(20, 8), nullable=False, default=0, server_default="0")
    discount = Column(Numeric(20, 8), nullable=False, default=0, server_default="0")
    payment_terms = Column(String(120), nullable=True)
    delivery_days = Column(Integer, nullable=True)
    valid_until = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    quotation = relationship("PurchaseQuotation", back_populates="offers")
    line = relationship("PurchaseQuotationLine", overlaps="offers,quotation")
    supplier = relationship("InventorySupplier", overlaps="line,offers,quotation")
