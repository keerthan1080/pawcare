from datetime import datetime
from typing import List, Optional
from fastapi import status

from app.core.context import get_correlation_id
from app.core.exceptions import AppException
from app.database.connection import DatabaseManager
from app.modules.availability.repository import AvailabilityRepository, AvailabilitySlotRecord
from app.modules.availability.schemas import (
    AvailabilitySlotCreateRequest,
    AvailabilitySlotResponse,
)
from app.modules.caregivers.repository import CaregiverRepository
from app.modules.users.repository import UserRecord, UserRepository


class AvailabilityService:
    """Business logic for caregiver availability windows and overlap prevention."""

    def __init__(self, db: DatabaseManager) -> None:
        self._repo = AvailabilityRepository(db)
        self._cg_repo = CaregiverRepository(db)
        self._user_repo = UserRepository(db)

    @staticmethod
    def _to_response(slot: AvailabilitySlotRecord) -> AvailabilitySlotResponse:
        remaining = max(slot.max_capacity - slot.booked_count, 0)
        return AvailabilitySlotResponse(
            id=slot.id,
            caregiver_id=slot.caregiver_id,
            start_time=slot.start_time,
            end_time=slot.end_time,
            max_capacity=slot.max_capacity,
            booked_count=slot.booked_count,
            remaining_capacity=remaining,
            is_available=slot.is_available and remaining > 0,
            notes=slot.notes,
            created_at=slot.created_at,
            updated_at=slot.updated_at,
        )

    def create_slot(
        self,
        current_user: UserRecord,
        payload: AvailabilitySlotCreateRequest,
    ) -> AvailabilitySlotResponse:
        cg = self._cg_repo.get_by_user_id(current_user.id)
        if cg is None or not cg.is_active:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CAREGIVER_PROFILE_NOT_FOUND",
                message="Create a caregiver profile before configuring availability slots.",
            )

        if payload.end_time <= payload.start_time:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_TIME_RANGE",
                message="Availability end_time must be strictly after start_time.",
            )

        start_iso = payload.start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = payload.end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        if self._repo.has_overlapping_slot(cg.id, start_iso, end_iso):
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="AVAILABILITY_OVERLAP",
                message="The requested availability window overlaps with an existing slot.",
            )

        slot = self._repo.create_slot(
            caregiver_id=cg.id,
            start_iso=start_iso,
            end_iso=end_iso,
            max_capacity=payload.max_capacity,
            notes=payload.notes,
        )
        self._user_repo.create_audit_log(
            actor_user_id=current_user.id,
            action="AVAILABILITY_SLOT_CREATED",
            entity_type="AVAILABILITY",
            entity_id=slot.id,
            correlation_id=get_correlation_id() or None,
            metadata={"caregiver_id": cg.id, "start_time": start_iso, "end_time": end_iso},
        )
        return self._to_response(slot)

    def list_caregiver_availability(
        self,
        caregiver_id: str,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        only_open: bool = True,
    ) -> List[AvailabilitySlotResponse]:
        cg = self._cg_repo.get_by_id(caregiver_id)
        if cg is None or not cg.is_active:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CAREGIVER_NOT_FOUND",
                message="Caregiver was not found.",
            )
        from_iso = from_time.strftime("%Y-%m-%dT%H:%M:%SZ") if from_time else None
        to_iso = to_time.strftime("%Y-%m-%dT%H:%M:%SZ") if to_time else None
        slots = self._repo.list_slots_for_caregiver(
            caregiver_id=caregiver_id,
            from_iso=from_iso,
            to_iso=to_iso,
            only_open=only_open,
        )
        return [self._to_response(s) for s in slots]

    def delete_slot(self, current_user: UserRecord, slot_id: str) -> None:
        cg = self._cg_repo.get_by_user_id(current_user.id)
        slot = self._repo.get_by_id(slot_id)
        if slot is None or cg is None or slot.caregiver_id != cg.id:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="AVAILABILITY_SLOT_NOT_FOUND",
                message="Availability slot was not found.",
            )
        if slot.booked_count > 0:
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="SLOT_HAS_ACTIVE_BOOKINGS",
                message="Cannot delete an availability slot that has active bookings.",
            )
        self._repo.delete_slot(slot_id)
