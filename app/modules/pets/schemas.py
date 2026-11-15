import re
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator

from app.common.enums import MedicalRecordType, PetGender, PetSpecies

TIME_24H_REGEX = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
ISO_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FeedingScheduleItem(BaseModel):
    time: str = Field(..., description="24-hour time in HH:MM format, e.g. '07:30'")
    meal: str = Field(..., min_length=1, max_length=100, description="e.g. 'Breakfast'")
    portion: Optional[str] = Field(default=None, max_length=100, description="e.g. '1.5 cups dry kibble'")
    notes: Optional[str] = Field(default=None, max_length=255)

    @validator("time")
    def validate_time_format(cls, v: str) -> str:
        cleaned = v.strip()
        if not TIME_24H_REGEX.match(cleaned):
            raise ValueError("Schedule time must be in 24-hour HH:MM format (e.g. '07:30').")
        return cleaned


class WalkingScheduleItem(BaseModel):
    time: str = Field(..., description="24-hour time in HH:MM format, e.g. '09:00'")
    duration_minutes: int = Field(default=30, ge=5, le=240)
    notes: Optional[str] = Field(default=None, max_length=255)

    @validator("time")
    def validate_walk_time(cls, v: str) -> str:
        cleaned = v.strip()
        if not TIME_24H_REGEX.match(cleaned):
            raise ValueError("Walk time must be in 24-hour HH:MM format (e.g. '09:00').")
        return cleaned


class PetMediaCreateRequest(BaseModel):
    media_type: str = Field(..., description="PHOTO or VIDEO")
    title: str = Field(..., min_length=2, max_length=150)
    url: str = Field(..., min_length=5, max_length=512)
    duration_seconds: Optional[int] = Field(default=None, ge=1, le=600)
    notes: Optional[str] = Field(default=None, max_length=500)

    @validator("media_type")
    def validate_media_type(cls, v: str) -> str:
        cleaned = (v or "").strip().upper()
        if cleaned not in ("PHOTO", "VIDEO"):
            raise ValueError("media_type must be either 'PHOTO' or 'VIDEO'.")
        return cleaned


class PetMediaResponse(PetMediaCreateRequest):
    id: str
    pet_id: str
    created_at: datetime


class EmergencyContactInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    relationship: str = Field(..., min_length=2, max_length=64)
    phone: str = Field(..., min_length=7, max_length=30)
    email: Optional[str] = Field(default=None, max_length=255)
    is_primary: bool = Field(default=True)


class EmergencyContactResponse(EmergencyContactInput):
    id: str
    pet_id: str
    created_at: datetime
    updated_at: datetime


class VeterinarianInput(BaseModel):
    clinic_name: str = Field(..., min_length=2, max_length=150)
    vet_name: Optional[str] = Field(default=None, max_length=120)
    phone: str = Field(..., min_length=7, max_length=30)
    address: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=500)


class VeterinarianResponse(VeterinarianInput):
    id: str
    pet_id: str
    created_at: datetime
    updated_at: datetime


class MedicalRecordCreateRequest(BaseModel):
    record_type: MedicalRecordType = Field(default=MedicalRecordType.VACCINATION)
    title: str = Field(..., min_length=2, max_length=150, description="e.g. 'Rabies Booster'")
    administered_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    expiry_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    provider_name: Optional[str] = Field(default=None, max_length=150)
    document_url: Optional[str] = Field(default=None, max_length=512)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @validator("administered_date", "expiry_date")
    def validate_iso_dates(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not ISO_DATE_REGEX.match(v):
                raise ValueError("Date must be in YYYY-MM-DD format.")
            date.fromisoformat(v)
        return v


class MedicalRecordResponse(MedicalRecordCreateRequest):
    id: str
    pet_id: str
    created_at: datetime


class PetCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    species: PetSpecies
    breed: Optional[str] = Field(default=None, max_length=100)
    gender: PetGender = Field(default=PetGender.UNKNOWN)
    date_of_birth: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    age_years: Optional[float] = Field(default=None, ge=0.0, le=50.0)
    weight_kg: Optional[float] = Field(default=None, gt=0.0, le=250.0)
    personality: Optional[str] = Field(default=None, max_length=1000)
    feeding_instructions: Optional[str] = Field(default=None, max_length=2000)
    feeding_schedule: List[FeedingScheduleItem] = Field(default_factory=list)
    walking_schedule: List[WalkingScheduleItem] = Field(default_factory=list)
    medication_instructions: Optional[str] = Field(default=None, max_length=2000)
    allergies: Optional[str] = Field(default=None, max_length=1000)
    behaviour_notes: Optional[str] = Field(default=None, max_length=2000)
    special_requirements: Optional[str] = Field(default=None, max_length=2000)
    additional_notes: Optional[str] = Field(default=None, max_length=2000)
    emergency_contacts: List[EmergencyContactInput] = Field(default_factory=list)
    preferred_veterinarian: Optional[VeterinarianInput] = Field(default=None)
    medical_records: List[MedicalRecordCreateRequest] = Field(default_factory=list)
    media_gallery: List[PetMediaCreateRequest] = Field(default_factory=list)

    @validator("name")
    def strip_pet_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Pet name cannot be blank.")
        return cleaned

    @validator("date_of_birth")
    def validate_dob(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not ISO_DATE_REGEX.match(v):
                raise ValueError("date_of_birth must be in YYYY-MM-DD format.")
            dob = date.fromisoformat(v)
            if dob > date.today():
                raise ValueError("date_of_birth cannot be in the future.")
        return v


class PetUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    breed: Optional[str] = Field(default=None, max_length=100)
    gender: Optional[PetGender] = None
    date_of_birth: Optional[str] = None
    age_years: Optional[float] = Field(default=None, ge=0.0, le=50.0)
    weight_kg: Optional[float] = Field(default=None, gt=0.0, le=250.0)
    personality: Optional[str] = Field(default=None, max_length=1000)
    feeding_instructions: Optional[str] = Field(default=None, max_length=2000)
    feeding_schedule: Optional[List[FeedingScheduleItem]] = None
    walking_schedule: Optional[List[WalkingScheduleItem]] = None
    medication_instructions: Optional[str] = Field(default=None, max_length=2000)
    allergies: Optional[str] = Field(default=None, max_length=1000)
    behaviour_notes: Optional[str] = Field(default=None, max_length=2000)
    special_requirements: Optional[str] = Field(default=None, max_length=2000)
    additional_notes: Optional[str] = Field(default=None, max_length=2000)

    @validator("date_of_birth")
    def validate_dob(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not ISO_DATE_REGEX.match(v):
                raise ValueError("date_of_birth must be in YYYY-MM-DD format.")
            dob = date.fromisoformat(v)
            if dob > date.today():
                raise ValueError("date_of_birth cannot be in the future.")
        return v


class PetEmergencyInfoUpdateRequest(BaseModel):
    allergies: Optional[str] = Field(default=None, max_length=1000)
    medication_instructions: Optional[str] = Field(default=None, max_length=2000)
    special_requirements: Optional[str] = Field(default=None, max_length=2000)
    emergency_contacts: List[EmergencyContactInput] = Field(default_factory=list)
    preferred_veterinarian: Optional[VeterinarianInput] = Field(default=None)


class PetPhotoUploadRequest(BaseModel):
    content_type: str = Field(..., description="image/jpeg, image/png, or image/webp")
    data_base64: str = Field(..., min_length=4, description="Base64-encoded image bytes")


class PetPhotoUploadResponse(BaseModel):
    pet_id: str
    photo_url: str
    object_key: str
    content_type: str
    size_bytes: int


class PetResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    species: PetSpecies
    breed: Optional[str] = None
    gender: PetGender
    date_of_birth: Optional[str] = None
    age_years: Optional[float] = None
    weight_kg: Optional[float] = None
    photo_url: Optional[str] = None
    personality: Optional[str] = None
    feeding_instructions: Optional[str] = None
    feeding_schedule: List[FeedingScheduleItem] = Field(default_factory=list)
    walking_schedule: List[WalkingScheduleItem] = Field(default_factory=list)
    medication_instructions: Optional[str] = None
    allergies: Optional[str] = None
    behaviour_notes: Optional[str] = None
    special_requirements: Optional[str] = None
    additional_notes: Optional[str] = None
    is_active: bool
    emergency_contacts: List[EmergencyContactResponse] = Field(default_factory=list)
    preferred_veterinarian: Optional[VeterinarianResponse] = None
    medical_records: List[MedicalRecordResponse] = Field(default_factory=list)
    media_gallery: List[PetMediaResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PetParentContactSummary(BaseModel):
    user_id: str
    full_name: str
    email: str
    phone: Optional[str] = None


class PetEmergencySummaryResponse(BaseModel):
    """Structured emergency action sheet (Section 14)."""

    pet_id: str
    pet_name: str
    species: PetSpecies
    breed: Optional[str] = None
    weight_kg: Optional[float] = None
    allergies: Optional[str] = None
    medication_instructions: Optional[str] = None
    special_requirements: Optional[str] = None
    pet_parent: PetParentContactSummary
    emergency_contacts: List[EmergencyContactResponse]
    preferred_veterinarian: Optional[VeterinarianResponse] = None
    medical_records: List[MedicalRecordResponse]
    medical_disclaimer: str = (
        "PawCare provides pet medical and emergency records for informational coordination only "
        "and does not diagnose medical conditions or provide veterinary treatment."
    )
