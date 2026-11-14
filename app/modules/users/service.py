from typing import Optional
from fastapi import status

from app.common.enums import UserRole
from app.common.pagination import PaginatedResponse
from app.core.context import get_correlation_id
from app.core.exceptions import AppException
from app.database.connection import DatabaseManager
from app.modules.users.repository import UserRecord, UserRepository
from app.modules.users.schemas import UserResponse, UserUpdateRequest


class UserService:
    """Business logic for user profile retrieval, updates, and admin user management."""

    def __init__(self, db: DatabaseManager) -> None:
        self._repo = UserRepository(db)

    @staticmethod
    def to_response(record: UserRecord) -> UserResponse:
        return UserResponse(
            id=record.id,
            email=record.email,
            full_name=record.full_name,
            phone=record.phone,
            role=UserRole(record.role),
            is_active=record.is_active,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def update_own_profile(self, current_user: UserRecord, payload: UserUpdateRequest) -> UserResponse:
        updated = self._repo.update_profile(
            user_id=current_user.id,
            full_name=payload.full_name,
            phone=payload.phone,
        )
        if not updated:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="USER_NOT_FOUND",
                message="User record was not found.",
            )
        self._repo.create_audit_log(
            actor_user_id=current_user.id,
            action="USER_PROFILE_UPDATED",
            entity_type="USER",
            entity_id=current_user.id,
            correlation_id=get_correlation_id() or None,
        )
        return self.to_response(updated)

    def list_users_for_admin(
        self,
        page: int = 1,
        size: int = 20,
        role: Optional[UserRole] = None,
    ) -> PaginatedResponse[UserResponse]:
        offset = (page - 1) * size
        records, total = self._repo.list_users(
            offset=offset,
            limit=size,
            role=role.value if role else None,
        )
        return PaginatedResponse[UserResponse](
            items=[self.to_response(r) for r in records],
            total=total,
            page=page,
            size=size,
        )

    def update_user_status_by_admin(
        self,
        admin_user: UserRecord,
        target_user_id: str,
        is_active: bool,
    ) -> UserResponse:
        if admin_user.id == target_user_id and not is_active:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="CANNOT_DEACTIVATE_SELF",
                message="Administrators cannot deactivate their own account.",
            )
        updated = self._repo.set_active_status(target_user_id, is_active=is_active)
        if not updated:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="USER_NOT_FOUND",
                message="Target user was not found.",
            )
        self._repo.create_audit_log(
            actor_user_id=admin_user.id,
            action="USER_ACTIVATED" if is_active else "USER_DEACTIVATED",
            entity_type="USER",
            entity_id=target_user_id,
            correlation_id=get_correlation_id() or None,
            metadata={"is_active": is_active},
        )
        return self.to_response(updated)
