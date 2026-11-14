"""FastAPI Authentication & Role-Based Authorization (RBAC) dependencies."""
from typing import Callable, Sequence
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.common.enums import UserRole
from app.core.exceptions import AppException
from app.database.connection import DatabaseManager, get_db
from app.modules.users.repository import UserRecord, UserRepository
from app.security.jwt import decode_jwt_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: DatabaseManager = Depends(get_db),
) -> UserRecord:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTHENTICATION_REQUIRED",
            message="Bearer authentication token is required.",
        )

    payload = decode_jwt_token(credentials.credentials, expected_type="access")
    user_id = payload.get("sub")
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="USER_NOT_FOUND",
            message="Authenticated user no longer exists.",
        )
    if not user.is_active:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="ACCOUNT_DEACTIVATED",
            message="User account is deactivated.",
        )
    return user


def require_roles(*allowed_roles: UserRole) -> Callable:
    allowed_values = {r.value for r in allowed_roles}

    def _role_guard(current_user: UserRecord = Depends(get_current_user)) -> UserRecord:
        if current_user.role not in allowed_values:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="INSUFFICIENT_PERMISSIONS",
                message=f"Role '{current_user.role}' is not authorized to access this resource.",
            )
        return current_user

    return _role_guard
