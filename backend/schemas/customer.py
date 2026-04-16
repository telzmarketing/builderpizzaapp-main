from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class AddressBase(BaseModel):
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


class CustomerOut(CustomerBase):
    id: str
    created_at: datetime
    updated_at: datetime
    addresses: list[AddressOut] = []

    model_config = {"from_attributes": True}
