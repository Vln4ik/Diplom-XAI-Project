from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.enums import UserStatus
from app.schemas.common import SchemaModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class UserSummary(SchemaModel):
    id: str
    full_name: str
    email: str
    status: UserStatus
    last_login_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserSummary
