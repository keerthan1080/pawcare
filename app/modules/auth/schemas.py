import re
from typing import Optional
from pydantic import BaseModel, Field, validator

from app.common.enums import UserRole
from app.modules.users.schemas import UserResponse

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_DIGITS_REGEX = re.compile(r"^\+?[0-9\-\s]{10,16}$")


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


class MobileOtpSendRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20, description="Mobile number e.g. +91-8247716995")
    role: UserRole = Field(default=UserRole.PET_PARENT)

    @validator("phone")
    def validate_phone(cls, v: str) -> str:
        cleaned = v.strip()
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Mobile number must contain 10 to 15 digits.")
        return cleaned

    @validator("role")
    def disallow_admin_self_otp(cls, v: UserRole) -> UserRole:
        if v == UserRole.ADMIN:
            raise ValueError("Self-registration as ADMIN via mobile OTP is not permitted.")
        return v


class MobileOtpSendResponse(BaseModel):
    phone: str
    expires_in_seconds: int
    delivery_channel: str = "SMS"
    message: str


class MobileOtpVerifyRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20)
    otp_code: str = Field(..., min_length=6, max_length=6)
    full_name: Optional[str] = Field(default=None, max_length=120)


class GoogleOAuthLoginRequest(BaseModel):
    id_token: str = Field(..., min_length=8, description="Google OAuth2 / OIDC ID token")
    email: str = Field(..., max_length=255)
    full_name: str = Field(default="Google User", min_length=2, max_length=120)
    role: UserRole = Field(default=UserRole.PET_PARENT)

    @validator("email")
    def validate_google_email(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not EMAIL_REGEX.match(cleaned):
            raise ValueError("Invalid Google email address.")
        return cleaned

    @validator("role")
    def disallow_admin_self_oauth(cls, v: UserRole) -> UserRole:
        if v == UserRole.ADMIN:
            raise ValueError("Public OAuth registration as ADMIN is not permitted.")
        return v


class OktaOAuthLoginRequest(BaseModel):
    id_token: str = Field(..., min_length=8, description="Okta OIDC ID token or authorization assertion")
    email: str = Field(..., max_length=255)
    full_name: str = Field(default="Okta SSO User", min_length=2, max_length=120)
    okta_issuer: Optional[str] = Field(default=None, max_length=255)
    role: UserRole = Field(default=UserRole.PET_PARENT)

    @validator("email")
    def validate_okta_email(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not EMAIL_REGEX.match(cleaned):
            raise ValueError("Invalid Okta email address.")
        return cleaned

    @validator("role")
    def disallow_admin_self_okta(cls, v: UserRole) -> UserRole:
        if v == UserRole.ADMIN:
            raise ValueError("Public Okta self-registration as ADMIN is not permitted.")
        return v


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
