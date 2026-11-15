from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator

from app.common.enums import (
    PetSpecies,
    PriceUnit,
    ServiceType,
    VerificationCategory,
    VerificationStatus,
)


class BoardingDetailsSchema(BaseModel):
    home_type: str = Field(..., min_length=2, max_length=80, description="e.g. 'Independent House' or 'Apartment'")
    has_fenced_yard: bool = Field(default=False)
    max_pets_hosted: int = Field(default=2, ge=1, le=20)
    is_smoke_free: bool = Field(default=True)
    has_resident_pets: bool = Field(default=False)
    notes: Optional[str] = Field(default=None, max_length=500)


class CaregiverServiceItemInput(BaseModel):
    service_type: ServiceType
    price_inr: float = Field(..., gt=0.0, le=100000.0, description="Price in INR")
    price_unit: PriceUnit
    duration_minutes: Optional[int] = Field(default=None, ge=15, le=1440)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: bool = Field(default=True)


class CaregiverServiceItemResponse(CaregiverServiceItemInput):
    id: str
    caregiver_id: str
    created_at: datetime
    updated_at: datetime


class CaregiverServicesPutRequest(BaseModel):
    services: List[CaregiverServiceItemInput] = Field(..., min_items=1, max_items=5)

    @validator("services")
    def ensure_unique_service_types(cls, v: List[CaregiverServiceItemInput]) -> List[CaregiverServiceItemInput]:
        seen = set()
        for item in v:
            if item.service_type in seen:
                raise ValueError(f"Duplicate service_type '{item.service_type.value}' in request.")
            seen.add(item.service_type)
        return v


class CaregiverProfileCreateRequest(BaseModel):
    bio: str = Field(..., min_length=10, max_length=2000)
    years_of_experience: int = Field(default=0, ge=0, le=60)
    experience_summary: Optional[str] = Field(default=None, max_length=2000)
    city: str = Field(..., min_length=2, max_length=80)
    locality: Optional[str] = Field(default=None, max_length=120)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    service_radius_km: float = Field(default=5.0, gt=0.0, le=100.0)
    supported_species: List[PetSpecies] = Field(..., min_items=1)
    max_pet_weight_kg: Optional[float] = Field(default=None, gt=0.0, le=200.0)
    special_capabilities: List[str] = Field(default_factory=list)
    boarding_details: Optional[BoardingDetailsSchema] = None
    services: List[CaregiverServiceItemInput] = Field(default_factory=list)

    @validator("city", "bio")
    def strip_text(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be blank.")
        return cleaned


class CaregiverProfileUpdateRequest(BaseModel):
    bio: Optional[str] = Field(default=None, min_length=10, max_length=2000)
    years_of_experience: Optional[int] = Field(default=None, ge=0, le=60)
    experience_summary: Optional[str] = Field(default=None, max_length=2000)
    city: Optional[str] = Field(default=None, min_length=2, max_length=80)
    locality: Optional[str] = Field(default=None, max_length=120)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    service_radius_km: Optional[float] = Field(default=None, gt=0.0, le=100.0)
    supported_species: Optional[List[PetSpecies]] = None
    max_pet_weight_kg: Optional[float] = Field(default=None, gt=0.0, le=200.0)
    special_capabilities: Optional[List[str]] = None
    boarding_details: Optional[BoardingDetailsSchema] = None


class CaregiverPhotoUploadRequest(BaseModel):
    content_type: str = Field(..., description="image/jpeg, image/png, or image/webp")
    data_base64: str = Field(..., min_length=4)


class CaregiverPhotoUploadResponse(BaseModel):
    caregiver_id: str
    profile_photo_url: str
    object_key: str
    content_type: str
    size_bytes: int


class CaregiverVerificationSubmitRequest(BaseModel):
    category: VerificationCategory
    document_reference: str = Field(..., min_length=3, max_length=512, description="Object key or reference ID")
    notes: Optional[str] = Field(default=None, max_length=1000)


class AdminVerificationReviewRequest(BaseModel):
    status: VerificationStatus = Field(..., description="VERIFIED, REJECTED, EXPIRED, or UNDER_REVIEW")
    review_notes: Optional[str] = Field(default=None, max_length=1000)
    expires_at: Optional[str] = Field(default=None, description="ISO 8601 UTC timestamp if applicable")


class AdminCaregiverStatusUpdateRequest(BaseModel):
    verification_status: VerificationStatus
    review_notes: Optional[str] = Field(default=None, max_length=1000)


class CaregiverVerificationResponse(BaseModel):
    id: str
    caregiver_id: str
    category: VerificationCategory
    document_reference: str
    notes: Optional[str] = None
    status: VerificationStatus
    reviewed_by_user_id: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CaregiverProfileResponse(BaseModel):
    id: str
    user_id: str
    full_name: str
    bio: str
    years_of_experience: int
    experience_summary: Optional[str] = None
    profile_photo_url: Optional[str] = None
    city: str
    locality: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    service_radius_km: float
    distance_km: Optional[float] = Field(
        default=None,
        description="Haversine distance in km when search coordinates (latitude, longitude) are provided.",
    )
    supported_species: List[PetSpecies]
    max_pet_weight_kg: Optional[float] = None
    special_capabilities: List[str]
    boarding_details: Optional[BoardingDetailsSchema] = None
    verification_status: VerificationStatus
    is_verified_badge: bool = Field(
        ...,
        description="Rule 5: True ONLY when backend verification_status == VERIFIED approved by an ADMIN.",
    )
    rating_average: float
    review_count: int
    services: List[CaregiverServiceItemResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CaregiverQuoteResponse(BaseModel):
    """Phase 4 Discovery quote & server-side availability check before booking."""

    caregiver_id: str
    caregiver_name: str
    is_verified_badge: bool
    service_type: ServiceType
    start_time: datetime
    end_time: datetime
    is_available: bool
    availability_slot_id: Optional[str] = None
    unit_price_inr: float
    price_unit: PriceUnit
    units_count: int
    subtotal_inr: float
    platform_commission_inr: float
    total_price_inr: float
