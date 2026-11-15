from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.common.enums import PetSpecies
from app.common.pagination import PaginatedResponse
from app.common.storage import StorageService, get_storage_service
from app.database.connection import DatabaseManager, get_db
from app.modules.pets.schemas import (
    MedicalRecordCreateRequest,
    MedicalRecordResponse,
    PetCreateRequest,
    PetEmergencyInfoUpdateRequest,
    PetEmergencySummaryResponse,
    PetMediaCreateRequest,
    PetMediaResponse,
    PetPhotoUploadRequest,
    PetPhotoUploadResponse,
    PetResponse,
    PetUpdateRequest,
)
from app.modules.pets.service import PetService
from app.modules.users.repository import UserRecord
from app.security.dependencies import get_current_user

router = APIRouter(prefix="/pets", tags=["Pets"])


@router.post("", response_model=PetResponse, status_code=status.HTTP_201_CREATED)
def create_pet_profile(
    payload: PetCreateRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> PetResponse:
    service = PetService(db)
    return service.create_pet(current_user, payload)


@router.get("", response_model=PaginatedResponse[PetResponse])
def list_pets(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    species: Optional[PetSpecies] = Query(default=None),
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> PaginatedResponse[PetResponse]:
    service = PetService(db)
    return service.list_my_pets(current_user, page=page, size=size, species=species)


@router.get("/{pet_id}", response_model=PetResponse)
def get_pet_profile(
    pet_id: str,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> PetResponse:
    service = PetService(db)
    return service.get_pet_by_id(current_user, pet_id)


@router.patch("/{pet_id}", response_model=PetResponse)
def update_pet_profile(
    pet_id: str,
    payload: PetUpdateRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> PetResponse:
    service = PetService(db)
    return service.update_pet(current_user, pet_id, payload)


@router.delete("/{pet_id}", response_model=PetResponse)
def deactivate_pet_profile(
    pet_id: str,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> PetResponse:
    service = PetService(db)
    return service.deactivate_pet(current_user, pet_id)


@router.post("/{pet_id}/photo", response_model=PetPhotoUploadResponse)
def upload_pet_photo(
    pet_id: str,
    payload: PetPhotoUploadRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> PetPhotoUploadResponse:
    service = PetService(db, storage=storage)
    return service.upload_pet_photo(current_user, pet_id, payload)


@router.post(
    "/{pet_id}/media",
    response_model=PetMediaResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_pet_media_item(
    pet_id: str,
    payload: PetMediaCreateRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> PetMediaResponse:
    service = PetService(db)
    return service.add_pet_media(current_user, pet_id, payload)


@router.get("/{pet_id}/media", response_model=List[PetMediaResponse])
def list_pet_media_items(
    pet_id: str,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> List[PetMediaResponse]:
    service = PetService(db)
    return service.list_pet_media(current_user, pet_id)


@router.post(
    "/{pet_id}/medical-records",
    response_model=MedicalRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_pet_medical_record(
    pet_id: str,
    payload: MedicalRecordCreateRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> MedicalRecordResponse:
    service = PetService(db)
    return service.add_medical_record(current_user, pet_id, payload)


@router.get("/{pet_id}/medical-records", response_model=List[MedicalRecordResponse])
def list_pet_medical_records(
    pet_id: str,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> List[MedicalRecordResponse]:
    service = PetService(db)
    return service.list_medical_records(current_user, pet_id)


@router.put("/{pet_id}/emergency-info", response_model=PetEmergencySummaryResponse)
def update_pet_emergency_info(
    pet_id: str,
    payload: PetEmergencyInfoUpdateRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> PetEmergencySummaryResponse:
    service = PetService(db)
    return service.update_emergency_info(current_user, pet_id, payload)


@router.get("/{pet_id}/emergency-info", response_model=PetEmergencySummaryResponse)
def get_pet_emergency_info(
    pet_id: str,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> PetEmergencySummaryResponse:
    service = PetService(db)
    return service.get_emergency_info(current_user, pet_id)
