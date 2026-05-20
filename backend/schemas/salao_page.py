from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SalaoExperienceCard(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=600)
    image: str = Field(default="", max_length=1000)


class SalaoMenuItem(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=600)


class SalaoPageSettingsOut(BaseModel):
    id: str
    enabled: bool
    hero_eyebrow: str
    hero_title: str
    hero_subtitle: str
    hero_description: str
    primary_cta_label: str
    secondary_cta_label: str
    hero_background_image: str
    hero_plate_image: str
    experience_eyebrow: str
    experience_title: str
    experience_text: str
    experience_cards: list[SalaoExperienceCard]
    menu_eyebrow: str
    menu_title: str
    menu_items: list[SalaoMenuItem]
    reservation_eyebrow: str
    reservation_title: str
    reservation_text: str
    reservation_background_image: str
    address: str
    hours: str
    phone: str
    whatsapp_url: str
    seo_title: str
    seo_description: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SalaoPageSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    hero_eyebrow: Optional[str] = Field(default=None, max_length=200)
    hero_title: Optional[str] = Field(default=None, max_length=200)
    hero_subtitle: Optional[str] = Field(default=None, max_length=300)
    hero_description: Optional[str] = None
    primary_cta_label: Optional[str] = Field(default=None, max_length=120)
    secondary_cta_label: Optional[str] = Field(default=None, max_length=120)
    hero_background_image: Optional[str] = Field(default=None, max_length=1000)
    hero_plate_image: Optional[str] = Field(default=None, max_length=1000)
    experience_eyebrow: Optional[str] = Field(default=None, max_length=120)
    experience_title: Optional[str] = Field(default=None, max_length=300)
    experience_text: Optional[str] = None
    experience_cards: Optional[list[SalaoExperienceCard]] = None
    menu_eyebrow: Optional[str] = Field(default=None, max_length=120)
    menu_title: Optional[str] = Field(default=None, max_length=300)
    menu_items: Optional[list[SalaoMenuItem]] = None
    reservation_eyebrow: Optional[str] = Field(default=None, max_length=120)
    reservation_title: Optional[str] = Field(default=None, max_length=300)
    reservation_text: Optional[str] = None
    reservation_background_image: Optional[str] = Field(default=None, max_length=1000)
    address: Optional[str] = Field(default=None, max_length=300)
    hours: Optional[str] = Field(default=None, max_length=300)
    phone: Optional[str] = Field(default=None, max_length=120)
    whatsapp_url: Optional[str] = Field(default=None, max_length=1000)
    seo_title: Optional[str] = Field(default=None, max_length=200)
    seo_description: Optional[str] = None
