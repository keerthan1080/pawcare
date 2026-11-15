from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, validator

from app.common.enums import BookingStatus, PriceUnit, ServiceType
from app.modules.pets.schemas import PetMediaResponse


class BookingCreateRequest(BaseModel):
    caregiver_id: str = Field(..., min_length=3)
    pet_id: str = Field(..., min_length=3)
    service_type: ServiceType
    start_time: datetime
    end_time: datetime
    special_instructions: Optional[str] = Field(default=None, max_length=2000)

    @validator("start_time", "end_time")
    def normalize_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class BookingStateTransitionRequest(BaseModel):
    target_status: BookingStatus
    reason: Optional[str] = Field(default=None, max_length=1000)


class AdminConfirmPaymentRequest(BaseModel):
    """Admin confirms payment after reviewing videos and photos uploaded by the Pet Owner."""

    media_reviewed: bool = Field(
        ...,
        description="Must be True: confirms Admin inspected the pet's profile photos and videos.",
    )
    review_notes: Optional[str] = Field(
        default="Verified pet profile videos & photos; payment confirmed by Admin.",
        max_length=1000,
    )


class AdminAssignCaregiverRequest(BaseModel):
    """Admin assigns or confirms the Caretaker after detailed review."""

    caregiver_id: str = Field(..., min_length=3, description="Verified caregiver ID assigned by Admin")
    assignment_notes: Optional[str] = Field(
        default="Caretaker assigned by Admin after detailed profile & media review.",
        max_length=1000,
    )


class BookingItemResponse(BaseModel):
    id: str
    booking_id: str
    item_type: str
    description: str
    quantity: int
    unit_amount_inr: float
    total_amount_inr: float
    created_at: datetime


class BookingResponse(BaseModel):
    id: str
    pet_parent_id: str
    pet_parent_name: Optional[str] = None
    pet_parent_phone: Optional[str] = None
    caregiver_id: str
    caregiver_name: Optional[str] = None
    pet_id: str
    pet_name: Optional[str] = None
    pet_media: List[PetMediaResponse] = Field(default_factory=list)
    availability_slot_id: Optional[str] = None
    service_type: ServiceType
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    unit_price_inr: float
    price_unit: PriceUnit
    units_count: int
    subtotal_inr: float
    platform_commission_inr: float
    caregiver_payout_inr: float
    total_price_inr: float
    special_instructions: Optional[str] = None
    cancellation_reason: Optional[str] = None
    media_reviewed_by_admin: bool = False
    admin_review_notes: Optional[str] = None
    assigned_by_admin_id: Optional[str] = None
    whatsapp_notification_url: Optional[str] = None
    items: List[BookingItemResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
