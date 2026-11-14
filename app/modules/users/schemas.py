from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator

from app.common.enums import UserRole


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    phone: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    phone: Optional[str] = Field(default=None, min_length=7, max_length=25)

    @validator("full_name")
    def strip_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) < 2:
                raise ValueError("Full name must contain at least 2 non-whitespace characters.")
        return v


class UserStatusUpdateRequest(BaseModel):
    is_active: bool
