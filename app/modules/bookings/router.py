from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from app.common.enums import BookingStatus
from app.common.pagination import PaginatedResponse
from app.database.connection import DatabaseManager, get_db
from app.modules.bookings.schemas import (
    BookingCreateRequest,
    BookingResponse,
    BookingStateTransitionRequest,
)
from app.modules.bookings.service import BookingService
from app.modules.users.repository import UserRecord
from app.security.dependencies import get_current_user

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreateRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> BookingResponse:
    service = BookingService(db)
    return service.create_booking(current_user, payload)


@router.get("", response_model=PaginatedResponse[BookingResponse])
def list_bookings(
    status: Optional[BookingStatus] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> PaginatedResponse[BookingResponse]:
    service = BookingService(db)
    return service.list_bookings(current_user, status_filter=status, page=page, size=size)


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking_details(
    booking_id: str,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> BookingResponse:
    service = BookingService(db)
    return service.get_booking(current_user, booking_id)


@router.patch("/{booking_id}/status", response_model=BookingResponse)
def update_booking_status(
    booking_id: str,
    payload: BookingStateTransitionRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> BookingResponse:
    service = BookingService(db)
    return service.transition_booking_state(current_user, booking_id, payload)
