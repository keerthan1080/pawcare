import base64
import json
from typing import List, Optional
from fastapi import status

from app.common.enums import (
    PetSpecies,
    PriceUnit,
    ServiceType,
    UserRole,
    VerificationCategory,
    VerificationStatus,
)
from app.common.pagination import PaginatedResponse
from app.common.storage import StorageService
from app.core.context import get_correlation_id
from app.core.exceptions import AppException
from app.database.connection import DatabaseManager
from app.modules.caregivers.repository import CaregiverRecord, CaregiverRepository
from app.modules.caregivers.schemas import (
    AdminCaregiverStatusUpdateRequest,
    AdminVerificationReviewRequest,
    BoardingDetailsSchema,
    CaregiverPhotoUploadRequest,
    CaregiverPhotoUploadResponse,
    CaregiverProfileCreateRequest,
    CaregiverProfileResponse,
    CaregiverProfileUpdateRequest,
    CaregiverServiceItemResponse,
    CaregiverServicesPutRequest,
    CaregiverVerificationResponse,
    CaregiverVerificationSubmitRequest,
)
from app.modules.users.repository import UserRecord, UserRepository


class CaregiverService:
    """Business logic for Caregiver Profiles, Services, Pricing, and Real Admin Verification (Rule 5)."""

    def __init__(self, db: DatabaseManager, storage: Optional[StorageService] = None) -> None:
        self._repo = CaregiverRepository(db)
        self._user_repo = UserRepository(db)
        self._storage = storage

    def _assemble_profile(self, record: CaregiverRecord) -> CaregiverProfileResponse:
        species_raw = json.loads(record.supported_species_json or "[]")
        capabilities_raw = json.loads(record.special_capabilities_json or "[]")
        boarding_raw = json.loads(record.boarding_details_json) if record.boarding_details_json else None
        service_records = self._repo.list_services(record.id)

        ver_status = VerificationStatus(record.verification_status)
        # Rule 5 — Verification Must Be Real:
        # Never display a "Verified" badge unless backend verification_status == VERIFIED
        is_verified_badge = ver_status == VerificationStatus.VERIFIED

        return CaregiverProfileResponse(
            id=record.id,
            user_id=record.user_id,
            full_name=record.full_name,
            bio=record.bio,
            years_of_experience=record.years_of_experience,
            experience_summary=record.experience_summary,
            profile_photo_url=record.profile_photo_url,
            city=record.city,
            locality=record.locality,
            latitude=record.latitude,
            longitude=record.longitude,
            service_radius_km=record.service_radius_km,
            supported_species=[PetSpecies(s) for s in species_raw],
            max_pet_weight_kg=record.max_pet_weight_kg,
            special_capabilities=capabilities_raw,
            boarding_details=BoardingDetailsSchema(**boarding_raw) if boarding_raw else None,
            verification_status=ver_status,
            is_verified_badge=is_verified_badge,
            rating_average=record.rating_average,
            review_count=record.review_count,
            services=[
                CaregiverServiceItemResponse(
                    id=s.id,
                    caregiver_id=s.caregiver_id,
                    service_type=ServiceType(s.service_type),
                    price_inr=s.price_inr,
                    price_unit=PriceUnit(s.price_unit),
                    duration_minutes=s.duration_minutes,
                    description=s.description,
                    is_active=s.is_active,
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                )
                for s in service_records
            ],
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _get_own_caregiver_or_404(self, user: UserRecord) -> CaregiverRecord:
        cg = self._repo.get_by_user_id(user.id)
        if cg is None or not cg.is_active:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CAREGIVER_PROFILE_NOT_FOUND",
                message="Caregiver profile has not been created for this user yet.",
            )
        return cg

    def create_profile(
        self,
        current_user: UserRecord,
        payload: CaregiverProfileCreateRequest,
    ) -> CaregiverProfileResponse:
        if current_user.role != UserRole.CAREGIVER.value:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="CAREGIVER_ROLE_REQUIRED",
                message="Only users registered with the CAREGIVER role can create a caregiver profile.",
            )

        existing = self._repo.get_by_user_id(current_user.id)
        if existing is not None:
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="CAREGIVER_PROFILE_ALREADY_EXISTS",
                message="A caregiver profile already exists for this account.",
            )

        cg = self._repo.create_caregiver(
            user_id=current_user.id,
            fields={
                "bio": payload.bio,
                "years_of_experience": payload.years_of_experience,
                "experience_summary": payload.experience_summary,
                "city": payload.city,
                "locality": payload.locality,
                "latitude": payload.latitude,
                "longitude": payload.longitude,
                "service_radius_km": payload.service_radius_km,
                "supported_species": [s.value for s in payload.supported_species],
                "max_pet_weight_kg": payload.max_pet_weight_kg,
                "special_capabilities": payload.special_capabilities,
                "boarding_details": payload.boarding_details.dict() if payload.boarding_details else None,
            },
        )

        if payload.services:
            self._repo.replace_services(
                caregiver_id=cg.id,
                services=[
                    {
                        **s.dict(),
                        "service_type": s.service_type.value,
                        "price_unit": s.price_unit.value,
                    }
                    for s in payload.services
                ],
            )

        self._user_repo.create_audit_log(
            actor_user_id=current_user.id,
            action="CAREGIVER_PROFILE_CREATED",
            entity_type="CAREGIVER",
            entity_id=cg.id,
            correlation_id=get_correlation_id() or None,
            metadata={"city": cg.city},
        )
        return self._assemble_profile(cg)

    def get_my_profile(self, current_user: UserRecord) -> CaregiverProfileResponse:
        cg = self._get_own_caregiver_or_404(current_user)
        return self._assemble_profile(cg)

    def get_public_profile(self, caregiver_id: str) -> CaregiverProfileResponse:
        cg = self._repo.get_by_id(caregiver_id)
        if cg is None or not cg.is_active:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CAREGIVER_NOT_FOUND",
                message="Requested caregiver profile was not found.",
            )
        return self._assemble_profile(cg)

    def update_my_profile(
        self,
        current_user: UserRecord,
        payload: CaregiverProfileUpdateRequest,
    ) -> CaregiverProfileResponse:
        cg = self._get_own_caregiver_or_404(current_user)
        raw = payload.dict(exclude_unset=True)
        db_updates = {}
        for k, v in raw.items():
            if k == "supported_species" and v is not None:
                db_updates["supported_species_json"] = json.dumps(
                    [s.value if hasattr(s, "value") else s for s in v]
                )
            elif k == "special_capabilities" and v is not None:
                db_updates["special_capabilities_json"] = json.dumps(v)
            elif k == "boarding_details":
                db_updates["boarding_details_json"] = json.dumps(v) if v is not None else None
            else:
                db_updates[k] = v

        updated = self._repo.update_caregiver(cg.id, db_updates)
        self._user_repo.create_audit_log(
            actor_user_id=current_user.id,
            action="CAREGIVER_PROFILE_UPDATED",
            entity_type="CAREGIVER",
            entity_id=cg.id,
            correlation_id=get_correlation_id() or None,
        )
        return self._assemble_profile(updated)  # type: ignore[arg-type]

    def set_my_services(
        self,
        current_user: UserRecord,
        payload: CaregiverServicesPutRequest,
    ) -> CaregiverProfileResponse:
        cg = self._get_own_caregiver_or_404(current_user)
        self._repo.replace_services(
            caregiver_id=cg.id,
            services=[
                {
                    **s.dict(),
                    "service_type": s.service_type.value,
                    "price_unit": s.price_unit.value,
                }
                for s in payload.services
            ],
        )
        self._user_repo.create_audit_log(
            actor_user_id=current_user.id,
            action="CAREGIVER_SERVICES_UPDATED",
            entity_type="CAREGIVER",
            entity_id=cg.id,
            correlation_id=get_correlation_id() or None,
            metadata={"service_count": len(payload.services)},
        )
        return self._assemble_profile(cg)

    def upload_my_photo(
        self,
        current_user: UserRecord,
        payload: CaregiverPhotoUploadRequest,
    ) -> CaregiverPhotoUploadResponse:
        cg = self._get_own_caregiver_or_404(current_user)
        if self._storage is None:
            raise AppException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="STORAGE_NOT_CONFIGURED",
                message="Object storage service is not configured.",
            )
        try:
            raw_bytes = base64.b64decode(payload.data_base64, validate=True)
        except Exception:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_BASE64_PAYLOAD",
                message="Image data_base64 is not valid base64.",
            )
        stored = self._storage.upload_image(
            namespace=f"caregivers/{cg.id}",
            content_type=payload.content_type,
            data=raw_bytes,
        )
        self._repo.update_caregiver(cg.id, {"profile_photo_url": stored.public_url})
        return CaregiverPhotoUploadResponse(
            caregiver_id=cg.id,
            profile_photo_url=stored.public_url,
            object_key=stored.object_key,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
        )

    def submit_verification(
        self,
        current_user: UserRecord,
        payload: CaregiverVerificationSubmitRequest,
    ) -> CaregiverVerificationResponse:
        cg = self._get_own_caregiver_or_404(current_user)
        rec = self._repo.create_verification(
            caregiver_id=cg.id,
            category=payload.category.value,
            document_reference=payload.document_reference,
            notes=payload.notes,
        )
        self._user_repo.create_audit_log(
            actor_user_id=current_user.id,
            action="CAREGIVER_VERIFICATION_SUBMITTED",
            entity_type="CAREGIVER_VERIFICATION",
            entity_id=rec.id,
            correlation_id=get_correlation_id() or None,
            metadata={"caregiver_id": cg.id, "category": rec.category},
        )
        return self._to_verification_response(rec)

    def list_my_verifications(self, current_user: UserRecord) -> List[CaregiverVerificationResponse]:
        cg = self._get_own_caregiver_or_404(current_user)
        return [self._to_verification_response(v) for v in self._repo.list_verifications(cg.id)]

    def admin_review_verification_item(
        self,
        admin_user: UserRecord,
        caregiver_id: str,
        verification_id: str,
        payload: AdminVerificationReviewRequest,
    ) -> CaregiverVerificationResponse:
        item = self._repo.get_verification_by_id(verification_id)
        if item is None or item.caregiver_id != caregiver_id:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="VERIFICATION_NOT_FOUND",
                message="Verification record was not found for this caregiver.",
            )
        updated = self._repo.review_verification_item(
            verification_id=verification_id,
            reviewer_user_id=admin_user.id,
            status_val=payload.status.value,
            review_notes=payload.review_notes,
            expires_at=payload.expires_at,
        )
        self._user_repo.create_audit_log(
            actor_user_id=admin_user.id,
            action="CAREGIVER_VERIFICATION_REVIEWED",
            entity_type="CAREGIVER_VERIFICATION",
            entity_id=verification_id,
            correlation_id=get_correlation_id() or None,
            metadata={"caregiver_id": caregiver_id, "status": payload.status.value},
        )
        return self._to_verification_response(updated)  # type: ignore[arg-type]

    def admin_set_caregiver_verification_status(
        self,
        admin_user: UserRecord,
        caregiver_id: str,
        payload: AdminCaregiverStatusUpdateRequest,
    ) -> CaregiverProfileResponse:
        cg = self._repo.get_by_id(caregiver_id)
        if cg is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CAREGIVER_NOT_FOUND",
                message="Caregiver profile was not found.",
            )
        updated = self._repo.update_caregiver(
            caregiver_id,
            {"verification_status": payload.verification_status.value},
        )
        self._user_repo.create_audit_log(
            actor_user_id=admin_user.id,
            action="CAREGIVER_STATUS_CHANGED",
            entity_type="CAREGIVER",
            entity_id=caregiver_id,
            correlation_id=get_correlation_id() or None,
            metadata={
                "verification_status": payload.verification_status.value,
                "review_notes": payload.review_notes,
            },
        )
        return self._assemble_profile(updated)  # type: ignore[arg-type]

    def search_caregivers(
        self,
        city: Optional[str] = None,
        service_type: Optional[ServiceType] = None,
        species: Optional[PetSpecies] = None,
        verified_only: bool = False,
        max_price_inr: Optional[float] = None,
        page: int = 1,
        size: int = 20,
    ) -> PaginatedResponse[CaregiverProfileResponse]:
        offset = (page - 1) * size
        records, total = self._repo.search_caregivers(
            city=city,
            service_type=service_type.value if service_type else None,
            species=species.value if species else None,
            verified_only=verified_only,
            max_price_inr=max_price_inr,
            offset=offset,
            limit=size,
        )
        return PaginatedResponse[CaregiverProfileResponse](
            items=[self._assemble_profile(r) for r in records],
            total=total,
            page=page,
            size=size,
        )

    @staticmethod
    def _to_verification_response(rec) -> CaregiverVerificationResponse:
        return CaregiverVerificationResponse(
            id=rec.id,
            caregiver_id=rec.caregiver_id,
            category=VerificationCategory(rec.category),
            document_reference=rec.document_reference,
            notes=rec.notes,
            status=VerificationStatus(rec.status),
            reviewed_by_user_id=rec.reviewed_by_user_id,
            review_notes=rec.review_notes,
            reviewed_at=rec.reviewed_at,
            expires_at=rec.expires_at,
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )
