from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, validator


class AvailabilitySlotCreateRequest(BaseModel):
    start_time: datetime
    end_time: datetime
    max_capacity: int = Field(default=1, ge=1, le=10)
    notes: Optional[str] = Field(default=None, max_length=255)

    @validator("start_time", "end_time")
    def normalize_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class AvailabilitySlotResponse(BaseModel):
    id: str
    caregiver_id: str
    start_time: datetime
    end_time: datetime
    max_capacity: int
    booked_count: int
    remaining_capacity: int
    is_available: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
