import base64
import json
import math
from datetime import datetime, timezone
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
    CaregiverQuoteResponse,
    CaregiverServiceItemResponse,
    CaregiverServicesPutRequest,
    CaregiverVerificationResponse,
    CaregiverVerificationSubmitRequest,
)
from app.modules.users.repository import UserRecord, UserRepository

PLATFORM_COMMISSION_RATE = 0.15  # 15% platform commission


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance in kilometers between two coordinates."""
    r_earth = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    return round(2.0 * r_earth * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)), 2)


def calculate_booking_units(price_unit: str, start_dt: datetime, end_dt: datetime) -> int:
    total_hours = max((end_dt - start_dt).total_seconds() / 3600.0, 0.5)
    if price_unit in (PriceUnit.PER_NIGHT.value, PriceUnit.PER_DAY.value):
        return max(1, math.ceil(total_hours / 24.0))
    return 1


class CaregiverService:
    """Business logic for Caregiver Profiles, Discovery Search, Quotes, and Real Admin Verification."""

    def __init__(self, db: DatabaseManager, storage: Optional[StorageService] = None) -> None:
        self._db = db
        self._repo = CaregiverRepository(db)
        self._user_repo = UserRepository(db)
        self._storage = storage

    def _assemble_profile(
        self,
        record: CaregiverRecord,
        distance_km: Optional[float] = None,
    ) -> CaregiverProfileResponse:
        species_raw = json.loads(record.supported_species_json or "[]")
        capabilities_raw = json.loads(record.special_capabilities_json or "[]")
        boarding_raw = json.loads(record.boarding_details_json) if record.boarding_details_json else None
        service_records = self._repo.list_services(record.id)

        ver_status = VerificationStatus(record.verification_status)
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
            distance_km=distance_km,
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
        locality: Optional[str] = None,
        service_type: Optional[ServiceType] = None,
        species: Optional[PetSpecies] = None,
        pet_weight_kg: Optional[float] = None,
        verified_only: bool = False,
        min_rating: Optional[float] = None,
        max_price_inr: Optional[float] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        max_distance_km: Optional[float] = None,
        sort_by: str = "recommended",
        page: int = 1,
        size: int = 20,
    ) -> PaginatedResponse[CaregiverProfileResponse]:
        start_iso = None
        end_iso = None
        if start_time or end_time:
            if not (start_time and end_time):
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="INCOMPLETE_TIME_WINDOW",
                    message="Both start_time and end_time must be provided when filtering by availability.",
                )
            s_utc = start_time.replace(tzinfo=timezone.utc) if start_time.tzinfo is None else start_time.astimezone(timezone.utc)
            e_utc = end_time.replace(tzinfo=timezone.utc) if end_time.tzinfo is None else end_time.astimezone(timezone.utc)
            if e_utc <= s_utc:
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="INVALID_TIME_RANGE",
                    message="end_time must be strictly after start_time.",
                )
            start_iso = s_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_iso = e_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        records = self._repo.search_caregivers(
            city=city,
            locality=locality,
            service_type=service_type.value if service_type else None,
            species=species.value if species else None,
            pet_weight_kg=pet_weight_kg,
            verified_only=verified_only,
            min_rating=min_rating,
            max_price_inr=max_price_inr,
            start_iso=start_iso,
            end_iso=end_iso,
        )

        assembled: List[CaregiverProfileResponse] = []
        for r in records:
            dist: Optional[float] = None
            if latitude is not None and longitude is not None and r.latitude is not None and r.longitude is not None:
                dist = haversine_km(latitude, longitude, r.latitude, r.longitude)
                limit_km = max_distance_km if max_distance_km is not None else r.service_radius_km
                if dist > limit_km:
                    continue
            assembled.append(self._assemble_profile(r, distance_km=dist))

        if sort_by == "distance_asc":
            assembled.sort(key=lambda c: (c.distance_km is None, c.distance_km or 999999.0))
        elif sort_by == "rating_desc":
            assembled.sort(key=lambda c: (-c.rating_average, -c.years_of_experience))
        elif sort_by == "price_asc":
            def _min_price(c: CaregiverProfileResponse) -> float:
                if service_type:
                    matching = [s.price_inr for s in c.services if s.service_type == service_type]
                    if matching:
                        return min(matching)
                return min((s.price_inr for s in c.services), default=999999.0)
            assembled.sort(key=_min_price)

        total = len(assembled)
        offset = (page - 1) * size
        paged = assembled[offset : offset + size]
        return PaginatedResponse[CaregiverProfileResponse](
            items=paged,
            total=total,
            page=page,
            size=size,
        )

    def get_service_quote(
        self,
        caregiver_id: str,
        service_type: ServiceType,
        start_time: datetime,
        end_time: datetime,
    ) -> CaregiverQuoteResponse:
        cg = self._repo.get_by_id(caregiver_id)
        if cg is None or not cg.is_active:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CAREGIVER_NOT_FOUND",
                message="Caregiver was not found.",
            )

        svc = self._repo.get_service_for_caregiver(caregiver_id, service_type.value)
        if svc is None:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="SERVICE_NOT_OFFERED",
                message=f"Caregiver does not offer service '{service_type.value}'.",
            )

        s_utc = start_time.replace(tzinfo=timezone.utc) if start_time.tzinfo is None else start_time.astimezone(timezone.utc)
        e_utc = end_time.replace(tzinfo=timezone.utc) if end_time.tzinfo is None else end_time.astimezone(timezone.utc)
        if e_utc <= s_utc:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_TIME_RANGE",
                message="end_time must be strictly after start_time.",
            )

        start_iso = s_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = e_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        with self._db.lock:
            cur = self._db.connection.execute(
                """
                SELECT id FROM availability
                WHERE caregiver_id = ?
                  AND is_available = 1
                  AND booked_count < max_capacity
                  AND start_time <= ?
                  AND end_time >= ?
                ORDER BY start_time ASC
                LIMIT 1
                """,
                (caregiver_id, start_iso, end_iso),
            )
            slot_row = cur.fetchone()

        units = calculate_booking_units(svc.price_unit, s_utc, e_utc)
        subtotal = round(svc.price_inr * units, 2)
        commission = round(subtotal * PLATFORM_COMMISSION_RATE, 2)

        return CaregiverQuoteResponse(
            caregiver_id=cg.id,
            caregiver_name=cg.full_name,
            is_verified_badge=cg.verification_status == VerificationStatus.VERIFIED.value,
            service_type=service_type,
            start_time=s_utc,
            end_time=e_utc,
            is_available=slot_row is not None,
            availability_slot_id=slot_row["id"] if slot_row else None,
            unit_price_inr=svc.price_inr,
            price_unit=PriceUnit(svc.price_unit),
            units_count=units,
            subtotal_inr=subtotal,
            platform_commission_inr=commission,
            total_price_inr=subtotal,
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
