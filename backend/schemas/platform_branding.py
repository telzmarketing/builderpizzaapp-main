"""Editable identity of the platform, separate from company configuration."""
from pydantic import BaseModel, ConfigDict, Field


class PlatformBranding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logo_url: str = Field(default="", max_length=200)
    favicon_url: str = Field(default="", max_length=200)


class PlatformBrandingUploadOut(BaseModel):
    url: str
