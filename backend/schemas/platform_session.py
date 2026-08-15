"""Allowlisted contract for the authenticated Master control-plane session."""
from pydantic import BaseModel


class PlatformSessionRoleOut(BaseModel):
    key: str
    name: str


class PlatformSessionOut(BaseModel):
    user_id: str
    roles: list[PlatformSessionRoleOut]
    permissions: list[str]
