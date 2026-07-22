from sqlalchemy import Column, String, Boolean, DateTime, Date, ForeignKey, Text, Integer, Float, Index, text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.database import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        Index("uq_customers_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_customers_tenant_email", "tenant_id", "email", unique=True),
        Index("uq_customers_tenant_google_id", "tenant_id", "google_id", unique=True,
              postgresql_where=text("google_id IS NOT NULL")),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_customers_tenant_id_tenants"), nullable=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    phone = Column(String(30))
    password_hash = Column(Text, nullable=True)
    google_id = Column(String(200), unique=True, nullable=True)
    lgpd_consent = Column(Boolean, default=False)
    lgpd_consent_at = Column(DateTime(timezone=True), nullable=True)
    lgpd_policy_version = Column(String(20), nullable=True)
    marketing_email_consent = Column(Boolean, default=False)
    marketing_whatsapp_consent = Column(Boolean, default=False)
    crm_status = Column(String(50), default="lead")
    source = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    tags = Column(Text, default="[]")
    last_contact_at = Column(DateTime(timezone=True), nullable=True)
    utm_source = Column(String(100), nullable=True)
    utm_campaign = Column(String(200), nullable=True)
    birth_date = Column(Date, nullable=True)
    first_order_at = Column(DateTime(timezone=True), nullable=True)
    last_order_at = Column(DateTime(timezone=True), nullable=True)
    total_orders = Column(Integer, default=0)
    total_spent = Column(Float, default=0.0)
    avg_ticket = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    addresses = relationship("Address", back_populates="customer")
    orders = relationship("Order", back_populates="customer")
    loyalty_account = relationship("CustomerLoyalty", back_populates="customer", uselist=False)
    payment_provider_customers = relationship("PaymentProviderCustomer", back_populates="customer")


class Address(Base):
    __tablename__ = "addresses"
    __table_args__ = (Index("uq_addresses_tenant_id_id", "tenant_id", "id", unique=True),)

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_addresses_tenant_id_tenants"), nullable=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    label = Column(String(100), nullable=True)
    street = Column(String(300), nullable=False)
    number = Column(String(20))
    complement = Column(String(100))
    neighborhood = Column(String(100))
    city = Column(String(100), nullable=False)
    state = Column(String(50))
    zip_code = Column(String(20))
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    customer = relationship("Customer", back_populates="addresses")
    orders = relationship("Order", back_populates="address")


class LgpdPolicy(Base):
    __tablename__ = "lgpd_policies"
    __table_args__ = (Index("uq_lgpd_policies_tenant_id_id", "tenant_id", "id", unique=True),)

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_lgpd_policies_tenant_id_tenants"), nullable=True)
    version = Column(String(20), nullable=False)
    title = Column(String(300), nullable=False, default="Política de Privacidade e Proteção de Dados")
    intro_text = Column(Text, nullable=True)
    data_controller_text = Column(Text, nullable=True)
    data_collected_text = Column(Text, nullable=True)
    data_usage_text = Column(Text, nullable=True)
    data_retention_text = Column(Text, nullable=True)
    rights_text = Column(Text, nullable=True)
    contact_text = Column(Text, nullable=True)
    marketing_email_label = Column(String(500), nullable=True, default="Desejo receber promoções e novidades por e-mail")
    marketing_whatsapp_label = Column(String(500), nullable=True, default="Desejo receber promoções e novidades pelo WhatsApp")
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
