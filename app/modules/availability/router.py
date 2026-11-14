from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status

from app.common.enums import UserRole
from app.database.connection import DatabaseManager, get_db
from app.modules.availability.schemas import (
    AvailabilitySlotCreateRequest,
    AvailabilitySlotResponse,
)
from app.modules.availability.service import AvailabilityService
from app.modules.users.repository import UserRecord
from app.security.dependencies import require_roles

router = APIRouter(prefix="/availability", tags=["Availability"])


@router.post("", response_model=AvailabilitySlotResponse, status_code=status.HTTP_201_CREATED)
def add_availability_slot(
    payload: AvailabilitySlotCreateRequest,
    current_user: UserRecord = Depends(require_roles(UserRole.CAREGIVER)),
    db: DatabaseManager = Depends(get_db),
) -> AvailabilitySlotResponse:
    service = AvailabilityService(db)
    return service.create_slot(current_user, payload)


@router.get("/caregiver/{caregiver_id}", response_model=List[AvailabilitySlotResponse])
def get_caregiver_availability(
    caregiver_id: str,
    from_time: Optional[datetime] = Query(default=None),
    to_time: Optional[datetime] = Query(default=None),
    only_open: bool = Query(default=True),
    db: DatabaseManager = Depends(get_db),
) -> List[AvailabilitySlotResponse]:
    service = AvailabilityService(db)
    return service.list_caregiver_availability(
        caregiver_id=caregiver_id,
        from_time=from_time,
        to_time=to_time,
        only_open=only_open,
    )


@router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_availability_slot(
    slot_id: str,
    current_user: UserRecord = Depends(require_roles(UserRole.CAREGIVER)),
    db: DatabaseManager = Depends(get_db),
) -> Response:
    service = AvailabilityService(db)
    service.delete_slot(current_user, slot_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
