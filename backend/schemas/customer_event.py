from __future__ import annotations
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CustomerEventCreate(BaseModel):
    customer_id: Optional[str] = None
    session_id: Optional[str] = None
    event_type: str
    event_name: Optional[str] = None
    event_description: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    product_id: Optional[str] = None
    order_id: Optional[str] = None
    campaign_id: Optional[str] = None
    coupon_id: Optional[str] = None
    metadata_json: Optional[str] = None
    source: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    device_type: Optional[str] = None
    browser: Optional[str] = None
    operating_system: Optional[str] = None
    ip_address: Optional[str] = None
    page_url: Optional[str] = None
    referrer_url: Optional[str] = None


class CustomerEventOut(BaseModel):
    id: str
    customer_id: Optional[str]
    session_id: Optional[str]
    event_type: str
    event_name: Optional[str]
    event_description: Optional[str]
    entity_type: Optional[str]
    entity_id: Optional[str]
    product_id: Optional[str]
    order_id: Optional[str]
    campaign_id: Optional[str]
    coupon_id: Optional[str]
    metadata_json: Optional[str]
    source: Optional[str]
    utm_source: Optional[str]
    utm_medium: Optional[str]
    utm_campaign: Optional[str]
    device_type: Optional[str]
    browser: Optional[str]
    page_url: Optional[str]
    referrer_url: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class IdentifySessionRequest(BaseModel):
    session_id: str
    customer_id: str
