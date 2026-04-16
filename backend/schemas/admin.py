from pydantic import BaseModel, EmailStr
from datetime import datetime


class AdminLoginIn(BaseModel):
    email: EmailStr
    password: str


class AdminOut(BaseModel):
    id: str
    email: str
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminOut
