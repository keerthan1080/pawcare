from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from app.common.enums import BookingStatus, UserRole
from app.common.pagination import PaginatedResponse
from app.database.connection import DatabaseManager, get_db
from app.modules.bookings.schemas import (
    AdminAssignCaregiverRequest,
    AdminConfirmPaymentRequest,
    BookingCreateRequest,
    BookingResponse,
    BookingStateTransitionRequest,
)
from app.modules.bookings.service import BookingService
from app.modules.users.repository import UserRecord
from app.security.dependencies import get_current_user, require_roles

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


@router.patch("/{booking_id}/admin-confirm-payment", response_model=BookingResponse)
def admin_confirm_booking_payment(
    booking_id: str,
    payload: AdminConfirmPaymentRequest,
    admin_user: UserRecord = Depends(require_roles(UserRole.ADMIN)),
    db: DatabaseManager = Depends(get_db),
) -> BookingResponse:
    """Admin confirms payment after inspecting the Pet Owner's profile videos and photos."""
    service = BookingService(db)
    return service.admin_confirm_payment_after_media_review(admin_user, booking_id, payload)


@router.patch("/{booking_id}/admin-assign-caregiver", response_model=BookingResponse)
def admin_assign_booking_caregiver(
    booking_id: str,
    payload: AdminAssignCaregiverRequest,
    admin_user: UserRecord = Depends(require_roles(UserRole.ADMIN)),
    db: DatabaseManager = Depends(get_db),
) -> BookingResponse:
    """Admin assigns or confirms the Caretaker after detailed review and payment confirmation."""
    service = BookingService(db)
    return service.admin_assign_caregiver_after_review(admin_user, booking_id, payload)


@router.patch("/{booking_id}/status", response_model=BookingResponse)
def update_booking_status(
    booking_id: str,
    payload: BookingStateTransitionRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> BookingResponse:
    service = BookingService(db)
    return service.transition_booking_state(current_user, booking_id, payload)


@router.post("/{booking_id}/demo-pay", response_model=BookingResponse)
def mark_booking_paid_without_gateway(
    booking_id: str,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> BookingResponse:
    service = BookingService(db)
    return service.mark_paid_for_demo(current_user, booking_id)
