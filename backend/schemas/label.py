from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LabelPrinterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=250)
    system_queue_hint: str | None = Field(default=None, max_length=200)
    printer_type: Literal["thermal", "desktop", "sheet"] = "thermal"
    connection_type: Literal["browser", "network", "installed", "shared", "local_service"] = "browser"
    manufacturer_model: str | None = Field(default=None, max_length=160)
    network_host: str | None = Field(default=None, max_length=255)
    network_port: int | None = Field(default=None, ge=1, le=65535)
    protocol: str | None = Field(default=None, max_length=30)
    max_width_mm: int | None = Field(default=None, ge=20, le=300)
    sector: Literal["dispatch"] = "dispatch"
    dpi: int = Field(default=203, ge=72, le=1200)
    active: bool = True
    is_default: bool = False


class LabelTemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    label_type: Literal["continuous", "gap", "black_mark", "roll", "sheet", "seal", "custom"] = "gap"
    width_mm: int = Field(default=100, ge=20, le=200)
    height_mm: int = Field(default=50, ge=20, le=300)
    margin_top_mm: int = Field(default=2, ge=0, le=20)
    margin_right_mm: int = Field(default=2, ge=0, le=20)
    margin_bottom_mm: int = Field(default=2, ge=0, le=20)
    margin_left_mm: int = Field(default=2, ge=0, le=20)
    safe_area_mm: int = Field(default=1, ge=0, le=20)
    gap_mm: int = Field(default=2, ge=0, le=50)
    columns: int = Field(default=1, ge=1, le=10)
    labels_per_sheet: int = Field(default=1, ge=1, le=100)
    dpi: int = Field(default=203, ge=72, le=1200)
    scale_percent: int = Field(default=100, ge=50, le=200)
    default_copies: int = Field(default=1, ge=1, le=20)
    font_scale_percent: int = Field(default=100, ge=50, le=200)
    offset_x_mm: int = Field(default=0, ge=-20, le=20)
    offset_y_mm: int = Field(default=0, ge=-20, le=20)
    rotation: Literal[0, 90, 180, 270] = 0
    density: int | None = Field(default=None, ge=0, le=30)
    speed: int | None = Field(default=None, ge=1, le=20)
    orientation: Literal["portrait", "landscape"] = "portrait"
    show_logo: bool = True
    show_printed_at: bool = True
    active: bool = True
    is_default: bool = False
    printer_ids: list[str] = Field(default_factory=list, max_length=100)


class LabelSettingsIn(BaseModel):
    include_drinks: bool = False
    require_reprint_reason: bool = True
    confirmation_required: bool = True
    batch_printing: bool = False
    default_printer_id: str | None = None
    default_template_id: str | None = None


class LabelVolumeRuleIn(BaseModel):
    scope_type: Literal["product", "category"]
    scope_value: str = Field(min_length=1, max_length=200)
    volumes_per_unit: int = Field(ge=0, le=20)
    active: bool = True


class LabelPrintIn(BaseModel):
    printer_id: str | None = None
    template_id: str | None = None
    copies: int = Field(default=1, ge=1, le=20)
    idempotency_key: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")


class LabelReprintIn(LabelPrintIn):
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value):
        if value is not None and len(value.strip()) < 3:
            raise ValueError("reason deve ter ao menos 3 caracteres")
        return value.strip() if value is not None else None


class LabelTestIn(LabelPrintIn):
    pass
