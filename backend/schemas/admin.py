from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class AdminLoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

    @field_validator("password")
    @classmethod
    def bcrypt_safe_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Senha excede o limite seguro de 72 bytes.")
        return value


class AdminOut(BaseModel):
    id: str
    email: str
    name: str
    active: bool
    phone: Optional[str] = None
    role_id: Optional[str] = None
    store_id: Optional[str] = None
    last_login_at: Optional[datetime] = None
    force_password_change: bool = False
    job_title: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminOut
    password_change_required: bool = False
