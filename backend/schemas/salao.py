from datetime import date, datetime, time
from typing import Literal, Optional

from pydantic import BaseModel, Field


TableStatus = Literal["available", "occupied", "reserved", "cleaning", "inactive"]
ReservationStatus = Literal["pending", "confirmed", "seated", "cancelled", "no_show", "completed"]
TableSessionStatus = Literal["open", "pending_payment", "paid", "closed", "cancelled"]


class RestaurantTableBase(BaseModel):
    number: str = Field(min_length=1, max_length=30)
    name: Optional[str] = Field(default=None, max_length=120)
    capacity: int = Field(default=2, ge=1, le=100)
    location: Optional[str] = Field(default=None, max_length=120)
    status: TableStatus = "available"
    active: bool = True


class RestaurantTableCreate(RestaurantTableBase):
    pass


class RestaurantTableUpdate(BaseModel):
    number: Optional[str] = Field(default=None, min_length=1, max_length=30)
    name: Optional[str] = Field(default=None, max_length=120)
    capacity: Optional[int] = Field(default=None, ge=1, le=100)
    location: Optional[str] = Field(default=None, max_length=120)
    status: Optional[TableStatus] = None
    active: Optional[bool] = None


class RestaurantTableStatusUpdate(BaseModel):
    status: TableStatus


class RestaurantTableOut(RestaurantTableBase):
    model_config = {"from_attributes": True}

    id: str
    created_at: datetime
    updated_at: datetime


class ReservationBase(BaseModel):
    customer_id: Optional[str] = None
    customer_name: str = Field(min_length=1, max_length=200)
    customer_phone: str = Field(min_length=1, max_length=40)
    customer_email: Optional[str] = Field(default=None, max_length=200)
    table_id: Optional[str] = None
    reservation_date: date
    reservation_time: time
    guests_count: int = Field(default=2, ge=1, le=100)
    status: ReservationStatus = "pending"
    notes: Optional[str] = None
    source: str = Field(default="salao", max_length=40)


class ReservationCreate(ReservationBase):
    pass


class PublicReservationCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=200)
    customer_phone: str = Field(min_length=1, max_length=40)
    customer_email: Optional[str] = Field(default=None, max_length=200)
    reservation_date: date
    reservation_time: time
    guests_count: int = Field(default=2, ge=1, le=100)
    notes: Optional[str] = None


class ReservationUpdate(BaseModel):
    customer_id: Optional[str] = None
    customer_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    customer_phone: Optional[str] = Field(default=None, min_length=1, max_length=40)
    customer_email: Optional[str] = Field(default=None, max_length=200)
    table_id: Optional[str] = None
    reservation_date: Optional[date] = None
    reservation_time: Optional[time] = None
    guests_count: Optional[int] = Field(default=None, ge=1, le=100)
    status: Optional[ReservationStatus] = None
    notes: Optional[str] = None
    source: Optional[str] = Field(default=None, max_length=40)


class ReservationStatusUpdate(BaseModel):
    status: ReservationStatus


class ReservationOut(ReservationBase):
    model_config = {"from_attributes": True}

    id: str
    created_at: datetime
    updated_at: datetime


class TableSessionBase(BaseModel):
    table_id: str
    customer_id: Optional[str] = None
    status: TableSessionStatus = "open"
    subtotal: float = Field(default=0.0, ge=0)
    service_fee: float = Field(default=0.0, ge=0)
    discount: float = Field(default=0.0, ge=0)
    total: float = Field(default=0.0, ge=0)
    waiter_name: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = None


class TableSessionCreate(TableSessionBase):
    pass


class TableSessionUpdate(BaseModel):
    customer_id: Optional[str] = None
    status: Optional[TableSessionStatus] = None
    subtotal: Optional[float] = Field(default=None, ge=0)
    service_fee: Optional[float] = Field(default=None, ge=0)
    discount: Optional[float] = Field(default=None, ge=0)
    total: Optional[float] = Field(default=None, ge=0)
    waiter_name: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = None


class TableSessionClose(BaseModel):
    subtotal: Optional[float] = Field(default=None, ge=0)
    service_fee: Optional[float] = Field(default=None, ge=0)
    discount: Optional[float] = Field(default=None, ge=0)
    total: Optional[float] = Field(default=None, ge=0)
    status: Literal["paid", "closed"] = "closed"
    notes: Optional[str] = None


class TableSessionOrderCreate(BaseModel):
    payment_method: Literal["cash", "debit_card", "credit_card", "pix"] = "cash"


class TableSessionOrderOut(BaseModel):
    order_id: str


class TableSessionPaymentConfirm(BaseModel):
    payment_method: Literal["cash", "debit_card", "credit_card", "pix"] = "cash"


class TableSessionItemBase(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=100)
    unit_price: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None


class TableSessionItemCreate(TableSessionItemBase):
    pass


class TableSessionItemUpdate(BaseModel):
    quantity: Optional[int] = Field(default=None, ge=1, le=100)
    unit_price: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None


class TableSessionItemOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    table_session_id: str
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    total_price: float
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TableSessionOut(TableSessionBase):
    model_config = {"from_attributes": True}

    id: str
    opened_at: datetime
    closed_at: Optional[datetime] = None
    items: list[TableSessionItemOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
