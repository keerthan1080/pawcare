from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.common.enums import UserRole
from app.common.pagination import PaginatedResponse
from app.database.connection import DatabaseManager, get_db
from app.modules.users.repository import UserRecord
from app.modules.users.schemas import (
    UserResponse,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)
from app.modules.users.service import UserService
from app.security.dependencies import get_current_user, require_roles

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def get_my_profile(current_user: UserRecord = Depends(get_current_user)) -> UserResponse:
    return UserService.to_response(current_user)


@router.patch("/me", response_model=UserResponse)
def update_my_profile(
    payload: UserUpdateRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> UserResponse:
    service = UserService(db)
    return service.update_own_profile(current_user, payload)


@router.get("", response_model=PaginatedResponse[UserResponse])
def list_users(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    role: Optional[UserRole] = Query(default=None),
    _admin: UserRecord = Depends(require_roles(UserRole.ADMIN)),
    db: DatabaseManager = Depends(get_db),
) -> PaginatedResponse[UserResponse]:
    service = UserService(db)
    return service.list_users_for_admin(page=page, size=size, role=role)


@router.patch("/{user_id}/status", response_model=UserResponse)
def set_user_active_status(
    user_id: str,
    payload: UserStatusUpdateRequest,
    admin_user: UserRecord = Depends(require_roles(UserRole.ADMIN)),
    db: DatabaseManager = Depends(get_db),
) -> UserResponse:
    service = UserService(db)
    return service.update_user_status_by_admin(admin_user, user_id, is_active=payload.is_active)
