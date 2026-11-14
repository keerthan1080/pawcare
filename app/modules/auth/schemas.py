import re
from typing import Optional
from pydantic import BaseModel, Field, validator

from app.common.enums import UserRole
from app.modules.users.schemas import UserResponse

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=120)
    phone: Optional[str] = Field(default=None, min_length=7, max_length=25)
    role: UserRole = Field(default=UserRole.PET_PARENT)

    @validator("email")
    def validate_email_format(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not EMAIL_REGEX.match(cleaned):
            raise ValueError("Invalid email address format.")
        return cleaned

    @validator("password")
    def validate_password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one letter and one digit.")
        return v

    @validator("role")
    def disallow_self_admin_registration(cls, v: UserRole) -> UserRole:
        if v == UserRole.ADMIN:
            raise ValueError("Public registration for ADMIN role is not permitted.")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
