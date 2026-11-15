import json
from typing import Dict, Optional, Set
from fastapi import status

from app.common.enums import (
    BookingStatus,
    PriceUnit,
    ServiceType,
    UserRole,
    VerificationStatus,
)
from app.common.pagination import PaginatedResponse
from app.core.context import get_correlation_id
from app.core.exceptions import AppException
from app.database.connection import DatabaseManager
from app.modules.bookings.repository import BookingRecord, BookingRepository
from app.modules.bookings.schemas import (
    BookingCreateRequest,
    BookingItemResponse,
    BookingResponse,
    BookingStateTransitionRequest,
)
from app.modules.caregivers.repository import CaregiverRepository
from app.modules.caregivers.service import PLATFORM_COMMISSION_RATE, calculate_booking_units
from app.modules.pets.repository import PetRepository
from app.modules.users.repository import UserRecord, UserRepository

# Section 11 & Rule 6 — Explicit Controlled Booking State Machine
VALID_BOOKING_TRANSITIONS: Dict[BookingStatus, Set[BookingStatus]] = {
    BookingStatus.DRAFT: {
        BookingStatus.PENDING_CONFIRMATION,
        BookingStatus.PAYMENT_PENDING,
        BookingStatus.CANCELLED,
    },
    BookingStatus.PENDING_CONFIRMATION: {
        BookingStatus.PAYMENT_PENDING,
        BookingStatus.CONFIRMED,
        BookingStatus.REJECTED,
        BookingStatus.CANCELLED,
    },
    BookingStatus.PAYMENT_PENDING: {
        BookingStatus.PAID,
        BookingStatus.CANCELLED,
        BookingStatus.REJECTED,
    },
    BookingStatus.PAID: {
        BookingStatus.CONFIRMED,
        BookingStatus.REFUND_PENDING,
        BookingStatus.DISPUTED,
    },
    BookingStatus.CONFIRMED: {
        BookingStatus.IN_PROGRESS,
        BookingStatus.CANCELLED,
        BookingStatus.REFUND_PENDING,
        BookingStatus.DISPUTED,
    },
    BookingStatus.IN_PROGRESS: {
        BookingStatus.COMPLETED,
        BookingStatus.DISPUTED,
    },
    BookingStatus.COMPLETED: {
        BookingStatus.DISPUTED,
        BookingStatus.REFUND_PENDING,
    },
    BookingStatus.REFUND_PENDING: {
        BookingStatus.REFUNDED,
        BookingStatus.DISPUTED,
    },
    BookingStatus.DISPUTED: {
        BookingStatus.REFUND_PENDING,
        BookingStatus.REFUNDED,
        BookingStatus.COMPLETED,
        BookingStatus.CANCELLED,
    },
    BookingStatus.CANCELLED: set(),
    BookingStatus.REJECTED: set(),
    BookingStatus.REFUNDED: set(),
}


class BookingService:
    """Business logic for Booking creation, Concurrency/Double-Booking Prevention, and State Machine."""

    def __init__(self, db: DatabaseManager) -> None:
        self._repo = BookingRepository(db)
        self._cg_repo = CaregiverRepository(db)
        self._pet_repo = PetRepository(db)
        self._user_repo = UserRepository(db)

    def _assemble_booking(self, rec: BookingRecord) -> BookingResponse:
        items = self._repo.list_booking_items(rec.id)
        return BookingResponse(
            id=rec.id,
            pet_parent_id=rec.pet_parent_id,
            caregiver_id=rec.caregiver_id,
            pet_id=rec.pet_id,
            availability_slot_id=rec.availability_slot_id,
            service_type=ServiceType(rec.service_type),
            start_time=rec.start_time,
            end_time=rec.end_time,
            status=BookingStatus(rec.status),
            unit_price_inr=rec.unit_price_inr,
            price_unit=PriceUnit(rec.price_unit),
            units_count=rec.units_count,
            subtotal_inr=rec.subtotal_inr,
            platform_commission_inr=rec.platform_commission_inr,
            caregiver_payout_inr=rec.caregiver_payout_inr,
            total_price_inr=rec.total_price_inr,
            special_instructions=rec.special_instructions,
            cancellation_reason=rec.cancellation_reason,
            items=[
                BookingItemResponse(
                    id=i.id,
                    booking_id=i.booking_id,
                    item_type=i.item_type,
                    description=i.description,
                    quantity=i.quantity,
                    unit_amount_inr=i.unit_amount_inr,
                    total_amount_inr=i.total_amount_inr,
                    created_at=i.created_at,
                )
                for i in items
            ],
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )

    def create_booking(
        self,
        current_user: UserRecord,
        payload: BookingCreateRequest,
    ) -> BookingResponse:
        if current_user.role != UserRole.PET_PARENT.value:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="PET_PARENT_ROLE_REQUIRED",
                message="Only Pet Parents can create bookings.",
            )

        if payload.end_time <= payload.start_time:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_TIME_RANGE",
                message="Booking end_time must be strictly after start_time.",
            )

        # 1. Verify Pet ownership & active state
        pet = self._pet_repo.get_by_id(payload.pet_id)
        if pet is None or not pet.is_active:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="PET_NOT_FOUND",
                message="Selected pet profile was not found.",
            )
        if pet.owner_id != current_user.id:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="PET_ACCESS_FORBIDDEN",
                message="You can only create a booking for your own pet.",
            )

        # 2. Verify Caregiver is active & VERIFIED (Rule 5 & Trust Principle)
        cg = self._cg_repo.get_by_id(payload.caregiver_id)
        if cg is None or not cg.is_active:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CAREGIVER_NOT_FOUND",
                message="Selected caregiver was not found.",
            )
        if cg.verification_status != VerificationStatus.VERIFIED.value:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="CAREGIVER_NOT_VERIFIED",
                message="Bookings can only be placed with verified caregivers.",
            )

        # 3. Verify Pet compatibility (species & max weight)
        supported_species = json.loads(cg.supported_species_json or "[]")
        if pet.species not in supported_species:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="UNSUPPORTED_PET_SPECIES",
                message=f"Selected caregiver does not support pet species '{pet.species}'.",
            )
        if cg.max_pet_weight_kg is not None and pet.weight_kg is not None:
            if pet.weight_kg > cg.max_pet_weight_kg:
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="PET_EXCEEDS_MAX_WEIGHT",
                    message=f"Pet weight ({pet.weight_kg} kg) exceeds caregiver's maximum limit ({cg.max_pet_weight_kg} kg).",
                )

        # 4. Server-side service & pricing calculation (Rule 2: Server Is Source of Truth)
        svc = self._cg_repo.get_service_for_caregiver(cg.id, payload.service_type.value)
        if svc is None:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="SERVICE_NOT_OFFERED",
                message=f"Selected caregiver does not offer '{payload.service_type.value}'.",
            )

        units = calculate_booking_units(svc.price_unit, payload.start_time, payload.end_time)
        subtotal = round(svc.price_inr * units, 2)
        commission = round(subtotal * PLATFORM_COMMISSION_RATE, 2)
        payout = round(subtotal - commission, 2)

        start_iso = payload.start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = payload.end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 5. Atomic availability validation & booking creation (Rule 1: No Double Booking)
        created = self._repo.create_booking_atomic(
            {
                "pet_parent_id": current_user.id,
                "caregiver_id": cg.id,
                "caregiver_user_id": cg.user_id,
                "pet_id": pet.id,
                "service_type": payload.service_type.value,
                "start_time": start_iso,
                "end_time": end_iso,
                "unit_price_inr": svc.price_inr,
                "price_unit": svc.price_unit,
                "units_count": units,
                "subtotal_inr": subtotal,
                "platform_commission_inr": commission,
                "caregiver_payout_inr": payout,
                "total_price_inr": subtotal,
                "special_instructions": payload.special_instructions,
            }
        )
        if created is None:
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="CAREGIVER_UNAVAILABLE",
                message="The selected caregiver is unavailable for the requested time.",
            )

        self._user_repo.create_audit_log(
            actor_user_id=current_user.id,
            action="BOOKING_CREATED",
            entity_type="BOOKING",
            entity_id=created.id,
            correlation_id=get_correlation_id() or None,
            metadata={
                "caregiver_id": cg.id,
                "pet_id": pet.id,
                "service_type": created.service_type,
                "total_price_inr": created.total_price_inr,
                "status": created.status,
            },
        )
        return self._assemble_booking(created)

    def get_booking(self, current_user: UserRecord, booking_id: str) -> BookingResponse:
        rec = self._repo.get_by_id(booking_id)
        if rec is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="BOOKING_NOT_FOUND",
                message="Booking was not found.",
            )
        self._ensure_can_access_booking(rec, current_user)
        return self._assemble_booking(rec)

    def list_bookings(
        self,
        current_user: UserRecord,
        status_filter: Optional[BookingStatus] = None,
        page: int = 1,
        size: int = 20,
    ) -> PaginatedResponse[BookingResponse]:
        offset = (page - 1) * size
        parent_id: Optional[str] = None
        cg_id: Optional[str] = None

        if current_user.role == UserRole.PET_PARENT.value:
            parent_id = current_user.id
        elif current_user.role == UserRole.CAREGIVER.value:
            cg = self._cg_repo.get_by_user_id(current_user.id)
            if cg is None:
                return PaginatedResponse[BookingResponse](items=[], total=0, page=page, size=size)
            cg_id = cg.id

        records, total = self._repo.list_bookings(
            pet_parent_id=parent_id,
            caregiver_id=cg_id,
            status_filter=status_filter.value if status_filter else None,
            offset=offset,
            limit=size,
        )
        return PaginatedResponse[BookingResponse](
            items=[self._assemble_booking(r) for r in records],
            total=total,
            page=page,
            size=size,
        )

    def transition_booking_state(
        self,
        current_user: UserRecord,
        booking_id: str,
        payload: BookingStateTransitionRequest,
    ) -> BookingResponse:
        rec = self._repo.get_by_id(booking_id)
        if rec is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="BOOKING_NOT_FOUND",
                message="Booking was not found.",
            )
        self._ensure_can_access_booking(rec, current_user)

        current_status = BookingStatus(rec.status)
        target_status = payload.target_status

        if current_status == BookingStatus.PAYMENT_PENDING and target_status == BookingStatus.CONFIRMED:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="PAYMENT_REQUIRED_BEFORE_CONFIRMATION",
                message="Booking payment must be verified before caregiver confirmation.",
            )

        allowed_next = VALID_BOOKING_TRANSITIONS.get(current_status, set())
        if target_status not in allowed_next:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_BOOKING_STATE_TRANSITION",
                message=f"Cannot transition booking from '{current_status.value}' to '{target_status.value}'.",
            )

        # Enforce role-level transition permissions
        self._validate_role_for_transition(current_user, current_status, target_status)

        cg = self._cg_repo.get_by_id(rec.caregiver_id)
        release_capacity = target_status in (BookingStatus.CANCELLED, BookingStatus.REJECTED)

        updated = self._repo.transition_status(
            booking_id=rec.id,
            new_status=target_status.value,
            reason=payload.reason,
            release_capacity=release_capacity,
            caregiver_user_id=cg.user_id if cg else None,
        )
        self._user_repo.create_audit_log(
            actor_user_id=current_user.id,
            action="BOOKING_STATUS_CHANGED",
            entity_type="BOOKING",
            entity_id=rec.id,
            correlation_id=get_correlation_id() or None,
            metadata={
                "from_status": current_status.value,
                "to_status": target_status.value,
                "reason": payload.reason,
            },
        )
        return self._assemble_booking(updated)  # type: ignore[arg-type]

    def _ensure_can_access_booking(self, rec: BookingRecord, user: UserRecord) -> None:
        if user.role == UserRole.ADMIN.value:
            return
        if user.role == UserRole.PET_PARENT.value and rec.pet_parent_id == user.id:
            return
        if user.role == UserRole.CAREGIVER.value:
            cg = self._cg_repo.get_by_user_id(user.id)
            if cg and cg.id == rec.caregiver_id:
                return
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="BOOKING_ACCESS_FORBIDDEN",
            message="You are not authorized to access this booking.",
        )

    @staticmethod
    def _validate_role_for_transition(
        user: UserRecord,
        current_status: BookingStatus,
        target_status: BookingStatus,
    ) -> None:
        if user.role == UserRole.ADMIN.value:
            return

        if user.role == UserRole.PET_PARENT.value:
            allowed_for_parent = {BookingStatus.CANCELLED, BookingStatus.DISPUTED}
            if target_status not in allowed_for_parent:
                raise AppException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="TRANSITION_NOT_ALLOWED_FOR_ROLE",
                    message=f"Pet Parent cannot transition booking to '{target_status.value}'.",
                )
            return

        if user.role == UserRole.CAREGIVER.value:
            allowed_for_caregiver = {
                BookingStatus.CONFIRMED,
                BookingStatus.REJECTED,
                BookingStatus.IN_PROGRESS,
                BookingStatus.COMPLETED,
                BookingStatus.DISPUTED,
            }
            if target_status not in allowed_for_caregiver:
                raise AppException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="TRANSITION_NOT_ALLOWED_FOR_ROLE",
                    message=f"Caregiver cannot transition booking to '{target_status.value}'.",
                )
            # Caregiver can only confirm a booking once payment is verified (PAID) or from PENDING_CONFIRMATION
            if target_status == BookingStatus.CONFIRMED and current_status not in (
                BookingStatus.PAID,
                BookingStatus.PENDING_CONFIRMATION,
            ):
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="PAYMENT_REQUIRED_BEFORE_CONFIRMATION",
                    message="Booking payment must be verified before caregiver confirmation.",
                )
