import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

def _hex(v: str) -> str:
    if not _HEX_RE.match(v):
        raise ValueError(f"Cor inválida: '{v}'. Use formato #RRGGBB.")
    return v.lower()


class ThemeSettingsOut(BaseModel):
    id: str
    primary: str
    secondary: str
    background_main: str
    background_alt: str
    background_card: str
    text_primary: str
    text_secondary: str
    text_muted: str
    status_success: str
    status_error: str
    status_warning: str
    status_info: str
    border: str
    interaction_hover: str
    interaction_active: str
    interaction_focus: str
    navbar: str
    footer: str
    sidebar: str
    modal: str
    overlay: str
    badge: str
    tag: str
    home_banner_background: str
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ThemeSettingsUpdate(BaseModel):
    primary: Optional[str] = None
    secondary: Optional[str] = None
    background_main: Optional[str] = None
    background_alt: Optional[str] = None
    background_card: Optional[str] = None
    text_primary: Optional[str] = None
    text_secondary: Optional[str] = None
    text_muted: Optional[str] = None
    status_success: Optional[str] = None
    status_error: Optional[str] = None
    status_warning: Optional[str] = None
    status_info: Optional[str] = None
    border: Optional[str] = None
    interaction_hover: Optional[str] = None
    interaction_active: Optional[str] = None
    interaction_focus: Optional[str] = None
    navbar: Optional[str] = None
    footer: Optional[str] = None
    sidebar: Optional[str] = None
    modal: Optional[str] = None
    overlay: Optional[str] = None
    badge: Optional[str] = None
    tag: Optional[str] = None
    home_banner_background: Optional[str] = None

    @field_validator(
        "primary", "secondary",
        "background_main", "background_alt", "background_card",
        "text_primary", "text_secondary", "text_muted",
        "status_success", "status_error", "status_warning", "status_info",
        "border",
        "interaction_hover", "interaction_active", "interaction_focus",
        "navbar", "footer", "sidebar", "modal", "overlay", "badge", "tag", "home_banner_background",
        mode="before",
    )
    @classmethod
    def validate_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _hex(v)
