from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import date, datetime


class AddressBase(BaseModel):
    label: Optional[str] = None
    street: str
    number: Optional[str] = None
    complement: Optional[str] = None
    neighborhood: Optional[str] = None
    city: str
    state: Optional[str] = None
    zip_code: Optional[str] = None
    is_default: bool = False


class AddressCreate(AddressBase):
    pass


class AddressOut(AddressBase):
    id: str
    customer_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


class CustomerOut(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    lgpd_consent: bool = False
    lgpd_policy_version: Optional[str] = None
    marketing_email_consent: bool = False
    marketing_whatsapp_consent: bool = False
    crm_status: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[str] = None
    last_contact_at: Optional[datetime] = None
    utm_source: Optional[str] = None
    utm_campaign: Optional[str] = None
    birth_date: Optional[date] = None
    first_order_at: Optional[datetime] = None
    last_order_at: Optional[datetime] = None
    total_orders: int = 0
    total_spent: float = 0.0
    avg_ticket: float = 0.0
    created_at: datetime
    updated_at: datetime
    addresses: list[AddressOut] = Field(default_factory=list)

    @field_validator("lgpd_consent", "marketing_email_consent", "marketing_whatsapp_consent", mode="before")
    @classmethod
    def _bool_or_false(cls, value):
        return False if value is None else value

    @field_validator("total_orders", mode="before")
    @classmethod
    def _int_or_zero(cls, value):
        return 0 if value is None else value

    @field_validator("total_spent", "avg_ticket", mode="before")
    @classmethod
    def _float_or_zero(cls, value):
        return 0.0 if value is None else value

    @field_validator("tags", mode="before")
    @classmethod
    def _tags_or_empty_list(cls, value):
        return "[]" if value is None else value

    model_config = {"from_attributes": True}


class CustomerChannelOut(BaseModel):
    id: str
    customer_id: str
    channel: str
    identifier: str
    normalized_identifier: str
    is_primary: bool
    marketing_consent: bool
    source: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WhatsAppLeadCreate(BaseModel):
    phone: str
    name: Optional[str] = None
    source: str = "whatsapp"


class CustomerIdentityOut(BaseModel):
    customer: CustomerOut
    channel: Optional[CustomerChannelOut] = None
    created: bool = False
    profile_level: str
