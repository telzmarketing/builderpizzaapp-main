from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class FiscalCompany(Base):
    __tablename__ = "fiscal_companies"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_fiscal_companies_tenant"), nullable=True)
    __table_args__ = (Index("uq_fiscal_companies_tenant_id_id", "tenant_id", "id", unique=True),)
    legal_name = Column(String(220), nullable=False)
    trade_name = Column(String(220), nullable=True)
    document = Column(String(20), nullable=False, index=True)
    state_registration = Column(String(40), nullable=True)
    municipal_registration = Column(String(40), nullable=True)
    tax_regime = Column(String(40), nullable=False, default="simples_nacional")
    cnae = Column(String(20), nullable=True)
    address_street = Column(String(220), nullable=True)
    address_number = Column(String(40), nullable=True)
    address_complement = Column(String(120), nullable=True)
    neighborhood = Column(String(120), nullable=True)
    city = Column(String(120), nullable=True)
    city_ibge_code = Column(String(20), nullable=True)
    state = Column(String(2), nullable=True)
    zip_code = Column(String(20), nullable=True)
    phone = Column(String(40), nullable=True)
    email = Column(String(180), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class FiscalCertificate(Base):
    __tablename__ = "fiscal_certificates"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_fiscal_certificates_tenant"), nullable=True)
    __table_args__ = (Index("uq_fiscal_certificates_tenant_id_id", "tenant_id", "id", unique=True),)
    certificate_type = Column(String(20), nullable=False, default="a1")
    subject_name = Column(String(220), nullable=True)
    serial_number = Column(String(120), nullable=True, index=True)
    valid_from = Column(Date, nullable=True)
    valid_until = Column(Date, nullable=True, index=True)
    storage_reference = Column(String(220), nullable=True)
    password_configured = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class FiscalSeries(Base):
    __tablename__ = "fiscal_series"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_fiscal_series_tenant"), nullable=True)
    document_model = Column(String(10), nullable=False, default="NFCe", index=True)
    series = Column(String(10), nullable=False, index=True)
    environment = Column(String(20), nullable=False, default="homologation", index=True)
    next_number = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (
        Index("uq_fiscal_series_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_mt_fiscal_series_model_env_series", "tenant_id", "document_model", "environment", "series", unique=True),
    )


class FiscalProductProfile(Base):
    __tablename__ = "fiscal_product_profiles"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_fiscal_product_profiles_tenant"), nullable=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    ncm = Column(String(10), nullable=False)
    cest = Column(String(10), nullable=True)
    cfop = Column(String(10), nullable=False, default="5102")
    origin = Column(String(2), nullable=False, default="0")
    cst = Column(String(4), nullable=True)
    csosn = Column(String(4), nullable=True)
    icms_rate = Column(Float, nullable=False, default=0.0)
    pis_cst = Column(String(4), nullable=True)
    pis_rate = Column(Float, nullable=False, default=0.0)
    cofins_cst = Column(String(4), nullable=True)
    cofins_rate = Column(Float, nullable=False, default=0.0)
    fiscal_description = Column(String(220), nullable=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    product = relationship("Product")
    __table_args__ = (
        Index("uq_fiscal_product_profiles_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_mt_fiscal_product_profile_product", "tenant_id", "product_id", unique=True),
    )


class FiscalDocument(Base):
    __tablename__ = "fiscal_documents"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_fiscal_documents_tenant"), nullable=True)
    order_id = Column(String, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id = Column(String, ForeignKey("fiscal_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    series_id = Column(String, ForeignKey("fiscal_series.id", ondelete="SET NULL"), nullable=True, index=True)
    document_model = Column(String(10), nullable=False, default="NFCe", index=True)
    environment = Column(String(20), nullable=False, default="homologation", index=True)
    status = Column(String(40), nullable=False, default="draft", index=True)
    operation_type = Column(String(40), nullable=False, default="sale")
    series = Column(String(10), nullable=True)
    number = Column(Integer, nullable=True, index=True)
    access_key = Column(String(60), nullable=True, index=True)
    issue_date = Column(DateTime(timezone=True), nullable=True, index=True)
    customer_name = Column(String(220), nullable=True)
    customer_document = Column(String(40), nullable=True)
    total_products = Column(Float, nullable=False, default=0.0)
    total_shipping = Column(Float, nullable=False, default=0.0)
    total_discount = Column(Float, nullable=False, default=0.0)
    total_document = Column(Float, nullable=False, default=0.0)
    xml_content = Column(Text, nullable=True)
    signed_xml_content = Column(Text, nullable=True)
    protocol = Column(String(120), nullable=True, index=True)
    rejection_reason = Column(Text, nullable=True)
    cancellation_protocol = Column(String(120), nullable=True)
    inutilization_protocol = Column(String(120), nullable=True)
    sefaz_status_code = Column(String(20), nullable=True)
    sefaz_status_message = Column(Text, nullable=True)
    snapshot_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    order = relationship("Order")
    company = relationship("FiscalCompany")
    series_ref = relationship("FiscalSeries")
    items = relationship("FiscalDocumentItem", cascade="all, delete-orphan", back_populates="document")
    events = relationship("FiscalDocumentEvent", cascade="all, delete-orphan", back_populates="document")
    __table_args__ = (Index("uq_fiscal_documents_tenant_id_id", "tenant_id", "id", unique=True),)


class FiscalDocumentItem(Base):
    __tablename__ = "fiscal_document_items"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_fiscal_document_items_tenant"), nullable=True)
    document_id = Column(String, ForeignKey("fiscal_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    description = Column(String(220), nullable=False)
    quantity = Column(Float, nullable=False, default=1.0)
    unit_price = Column(Float, nullable=False, default=0.0)
    total_price = Column(Float, nullable=False, default=0.0)
    ncm = Column(String(10), nullable=True)
    cest = Column(String(10), nullable=True)
    cfop = Column(String(10), nullable=True)
    origin = Column(String(2), nullable=True)
    cst = Column(String(4), nullable=True)
    csosn = Column(String(4), nullable=True)
    icms_rate = Column(Float, nullable=False, default=0.0)
    pis_cst = Column(String(4), nullable=True)
    pis_rate = Column(Float, nullable=False, default=0.0)
    cofins_cst = Column(String(4), nullable=True)
    cofins_rate = Column(Float, nullable=False, default=0.0)
    tax_profile_snapshot_json = Column(Text, nullable=False, default="{}")

    document = relationship("FiscalDocument", back_populates="items")
    product = relationship("Product")
    __table_args__ = (Index("uq_fiscal_document_items_tenant_id_id", "tenant_id", "id", unique=True),)


class FiscalDocumentEvent(Base):
    __tablename__ = "fiscal_document_events"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_fiscal_document_events_tenant"), nullable=True)
    document_id = Column(String, ForeignKey("fiscal_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(40), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="recorded", index=True)
    request_xml = Column(Text, nullable=True)
    response_xml = Column(Text, nullable=True)
    protocol = Column(String(120), nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    document = relationship("FiscalDocument", back_populates="events")
    __table_args__ = (Index("uq_fiscal_document_events_tenant_id_id", "tenant_id", "id", unique=True),)
