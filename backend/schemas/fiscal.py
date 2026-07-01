from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

FiscalEnvironment = Literal["homologation", "production"]
FiscalDocumentModel = Literal["NFCe", "NFe"]
FiscalDocumentStatus = Literal[
    "draft",
    "validated",
    "signed",
    "transmitting",
    "authorized",
    "rejected",
    "denied",
    "cancel_pending",
    "cancelled",
    "inutilized",
    "error",
]


class FiscalCompanyIn(BaseModel):
    legal_name: str = Field(min_length=1, max_length=220)
    trade_name: str | None = Field(default=None, max_length=220)
    document: str = Field(min_length=11, max_length=20)
    state_registration: str | None = Field(default=None, max_length=40)
    municipal_registration: str | None = Field(default=None, max_length=40)
    tax_regime: str = Field(default="simples_nacional", min_length=1, max_length=40)
    cnae: str | None = Field(default=None, max_length=20)
    address_street: str | None = Field(default=None, max_length=220)
    address_number: str | None = Field(default=None, max_length=40)
    address_complement: str | None = Field(default=None, max_length=120)
    neighborhood: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    city_ibge_code: str | None = Field(default=None, max_length=20)
    state: str | None = Field(default=None, max_length=2)
    zip_code: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=180)
    active: bool = True


class FiscalCompanyOut(FiscalCompanyIn):
    id: str
    tenant_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FiscalCertificateIn(BaseModel):
    certificate_type: Literal["a1", "a3"] = "a1"
    subject_name: str | None = Field(default=None, max_length=220)
    serial_number: str | None = Field(default=None, max_length=120)
    valid_from: date | None = None
    valid_until: date | None = None
    storage_reference: str | None = Field(default=None, max_length=220)
    password_configured: bool = False
    active: bool = True


class FiscalCertificateOut(FiscalCertificateIn):
    id: str
    tenant_id: str
    valid: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FiscalSeriesIn(BaseModel):
    document_model: FiscalDocumentModel = "NFCe"
    series: str = Field(min_length=1, max_length=10)
    environment: FiscalEnvironment = "homologation"
    next_number: int = Field(default=1, ge=1)
    active: bool = True
    notes: str | None = None


class FiscalSeriesOut(FiscalSeriesIn):
    id: str
    tenant_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FiscalProductProfileIn(BaseModel):
    product_id: str
    ncm: str = Field(min_length=2, max_length=10)
    cest: str | None = Field(default=None, max_length=10)
    cfop: str = Field(default="5102", min_length=4, max_length=10)
    origin: str = Field(default="0", min_length=1, max_length=2)
    cst: str | None = Field(default=None, max_length=4)
    csosn: str | None = Field(default=None, max_length=4)
    icms_rate: float = Field(default=0.0, ge=0)
    pis_cst: str | None = Field(default=None, max_length=4)
    pis_rate: float = Field(default=0.0, ge=0)
    cofins_cst: str | None = Field(default=None, max_length=4)
    cofins_rate: float = Field(default=0.0, ge=0)
    fiscal_description: str | None = Field(default=None, max_length=220)
    active: bool = True


class FiscalProductProfileOut(FiscalProductProfileIn):
    id: str
    tenant_id: str
    product_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FiscalDocumentItemOut(BaseModel):
    id: str
    product_id: str | None = None
    description: str
    quantity: float
    unit_price: float
    total_price: float
    ncm: str | None = None
    cest: str | None = None
    cfop: str | None = None
    origin: str | None = None
    cst: str | None = None
    csosn: str | None = None
    icms_rate: float
    pis_cst: str | None = None
    pis_rate: float
    cofins_cst: str | None = None
    cofins_rate: float


class FiscalDocumentEventOut(BaseModel):
    id: str
    event_type: str
    status: str
    protocol: str | None = None
    message: str | None = None
    created_at: datetime | None = None


class FiscalDocumentOut(BaseModel):
    id: str
    tenant_id: str
    order_id: str | None = None
    company_id: str | None = None
    series_id: str | None = None
    document_model: FiscalDocumentModel
    environment: FiscalEnvironment
    status: FiscalDocumentStatus | str
    operation_type: str
    series: str | None = None
    number: int | None = None
    access_key: str | None = None
    issue_date: datetime | None = None
    customer_name: str | None = None
    customer_document: str | None = None
    total_products: float
    total_shipping: float
    total_discount: float
    total_document: float
    protocol: str | None = None
    rejection_reason: str | None = None
    cancellation_protocol: str | None = None
    inutilization_protocol: str | None = None
    sefaz_status_code: str | None = None
    sefaz_status_message: str | None = None
    xml_content: str | None = None
    signed_xml_content: str | None = None
    items: list[FiscalDocumentItemOut] = []
    events: list[FiscalDocumentEventOut] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FiscalDocumentFromOrderIn(BaseModel):
    document_model: FiscalDocumentModel = "NFCe"
    environment: FiscalEnvironment = "homologation"
    series_id: str | None = None


class FiscalCancelIn(BaseModel):
    reason: str = Field(min_length=15, max_length=255)


class FiscalInvalidateIn(BaseModel):
    number: int = Field(ge=1)
    reason: str = Field(min_length=15, max_length=255)


class FiscalOverviewOut(BaseModel):
    company: FiscalCompanyOut | None = None
    certificate: FiscalCertificateOut | None = None
    series: list[FiscalSeriesOut]
    product_profiles: list[FiscalProductProfileOut]
    documents: list[FiscalDocumentOut]
    document_status_counts: dict[str, int]
    ready_for_homologation: bool
    missing_setup: list[str]
