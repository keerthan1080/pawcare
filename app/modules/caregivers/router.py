from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.common.enums import PetSpecies, ServiceType, UserRole
from app.common.pagination import PaginatedResponse
from app.common.storage import StorageService, get_storage_service
from app.database.connection import DatabaseManager, get_db
from app.modules.caregivers.schemas import (
    AdminCaregiverStatusUpdateRequest,
    AdminVerificationReviewRequest,
    CaregiverPhotoUploadRequest,
    CaregiverPhotoUploadResponse,
    CaregiverProfileCreateRequest,
    CaregiverProfileResponse,
    CaregiverProfileUpdateRequest,
    CaregiverServicesPutRequest,
    CaregiverVerificationResponse,
    CaregiverVerificationSubmitRequest,
)
from app.modules.caregivers.service import CaregiverService
from app.modules.users.repository import UserRecord
from app.security.dependencies import get_current_user, require_roles

router = APIRouter(prefix="/caregivers", tags=["Caregivers"])


@router.post("/me", response_model=CaregiverProfileResponse, status_code=status.HTTP_201_CREATED)
def create_my_caregiver_profile(
    payload: CaregiverProfileCreateRequest,
    current_user: UserRecord = Depends(require_roles(UserRole.CAREGIVER)),
    db: DatabaseManager = Depends(get_db),
) -> CaregiverProfileResponse:
    service = CaregiverService(db)
    return service.create_profile(current_user, payload)


@router.get("/me", response_model=CaregiverProfileResponse)
def get_my_caregiver_profile(
    current_user: UserRecord = Depends(require_roles(UserRole.CAREGIVER)),
    db: DatabaseManager = Depends(get_db),
) -> CaregiverProfileResponse:
    service = CaregiverService(db)
    return service.get_my_profile(current_user)


@router.patch("/me", response_model=CaregiverProfileResponse)
def update_my_caregiver_profile(
    payload: CaregiverProfileUpdateRequest,
    current_user: UserRecord = Depends(require_roles(UserRole.CAREGIVER)),
    db: DatabaseManager = Depends(get_db),
) -> CaregiverProfileResponse:
    service = CaregiverService(db)
    return service.update_my_profile(current_user, payload)


@router.put("/me/services", response_model=CaregiverProfileResponse)
def set_my_caregiver_services(
    payload: CaregiverServicesPutRequest,
    current_user: UserRecord = Depends(require_roles(UserRole.CAREGIVER)),
    db: DatabaseManager = Depends(get_db),
) -> CaregiverProfileResponse:
    service = CaregiverService(db)
    return service.set_my_services(current_user, payload)


@router.post("/me/photo", response_model=CaregiverPhotoUploadResponse)
def upload_my_caregiver_photo(
    payload: CaregiverPhotoUploadRequest,
    current_user: UserRecord = Depends(require_roles(UserRole.CAREGIVER)),
    db: DatabaseManager = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> CaregiverPhotoUploadResponse:
    service = CaregiverService(db, storage=storage)
    return service.upload_my_photo(current_user, payload)


@router.post(
    "/me/verifications",
    response_model=CaregiverVerificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_caregiver_verification(
    payload: CaregiverVerificationSubmitRequest,
    current_user: UserRecord = Depends(require_roles(UserRole.CAREGIVER)),
    db: DatabaseManager = Depends(get_db),
) -> CaregiverVerificationResponse:
    service = CaregiverService(db)
    return service.submit_verification(current_user, payload)


@router.get("/me/verifications", response_model=List[CaregiverVerificationResponse])
def list_my_caregiver_verifications(
    current_user: UserRecord = Depends(require_roles(UserRole.CAREGIVER)),
    db: DatabaseManager = Depends(get_db),
) -> List[CaregiverVerificationResponse]:
    service = CaregiverService(db)
    return service.list_my_verifications(current_user)


@router.patch(
    "/{caregiver_id}/verifications/{verification_id}",
    response_model=CaregiverVerificationResponse,
)
def admin_review_verification(
    caregiver_id: str,
    verification_id: str,
    payload: AdminVerificationReviewRequest,
    admin_user: UserRecord = Depends(require_roles(UserRole.ADMIN)),
    db: DatabaseManager = Depends(get_db),
) -> CaregiverVerificationResponse:
    service = CaregiverService(db)
    return service.admin_review_verification_item(admin_user, caregiver_id, verification_id, payload)


@router.patch("/{caregiver_id}/verification-status", response_model=CaregiverProfileResponse)
def admin_update_caregiver_verification_status(
    caregiver_id: str,
    payload: AdminCaregiverStatusUpdateRequest,
    admin_user: UserRecord = Depends(require_roles(UserRole.ADMIN)),
    db: DatabaseManager = Depends(get_db),
) -> CaregiverProfileResponse:
    service = CaregiverService(db)
    return service.admin_set_caregiver_verification_status(admin_user, caregiver_id, payload)


@router.get("", response_model=PaginatedResponse[CaregiverProfileResponse])
def search_caregivers(
    city: Optional[str] = Query(default=None),
    service_type: Optional[ServiceType] = Query(default=None),
    species: Optional[PetSpecies] = Query(default=None),
    verified_only: bool = Query(default=False),
    max_price_inr: Optional[float] = Query(default=None, gt=0.0),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: DatabaseManager = Depends(get_db),
) -> PaginatedResponse[CaregiverProfileResponse]:
    service = CaregiverService(db)
    return service.search_caregivers(
        city=city,
        service_type=service_type,
        species=species,
        verified_only=verified_only,
        max_price_inr=max_price_inr,
        page=page,
        size=size,
    )


@router.get("/{caregiver_id}", response_model=CaregiverProfileResponse)
def get_caregiver_public_profile(
    caregiver_id: str,
    db: DatabaseManager = Depends(get_db),
) -> CaregiverProfileResponse:
    service = CaregiverService(db)
    return service.get_public_profile(caregiver_id)
