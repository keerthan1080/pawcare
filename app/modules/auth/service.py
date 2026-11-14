from fastapi import status

from app.config.settings import get_settings
from app.core.context import get_correlation_id
from app.core.exceptions import AppException
from app.database.connection import DatabaseManager
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenPairResponse,
)
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService
from app.security.jwt import create_jwt_token, decode_jwt_token
from app.security.passwords import hash_password, verify_password


class AuthService:
    """Business logic for user registration, authentication, token refresh, and audit logging."""

    def __init__(self, db: DatabaseManager) -> None:
        self._repo = UserRepository(db)
        self._settings = get_settings()

    def register(self, payload: RegisterRequest) -> TokenPairResponse:
        existing = self._repo.get_by_email(payload.email)
        if existing is not None:
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="EMAIL_ALREADY_REGISTERED",
                message="An account with this email address already exists.",
            )

        password_hash = hash_password(payload.password)
        user = self._repo.create_user(
            email=payload.email,
            full_name=payload.full_name,
            phone=payload.phone,
            password_hash=password_hash,
            role=payload.role.value,
        )
        self._repo.create_audit_log(
            actor_user_id=user.id,
            action="USER_REGISTERED",
            entity_type="USER",
            entity_id=user.id,
            correlation_id=get_correlation_id() or None,
            metadata={"role": user.role},
        )
        return self._issue_tokens(user)

    def login(self, payload: LoginRequest) -> TokenPairResponse:
        user = self._repo.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.password_hash):
            raise AppException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="INVALID_CREDENTIALS",
                message="Invalid email or password.",
            )

        if not user.is_active:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="ACCOUNT_DEACTIVATED",
                message="User account is deactivated.",
            )

        self._repo.create_audit_log(
            actor_user_id=user.id,
            action="USER_LOGGED_IN",
            entity_type="USER",
            entity_id=user.id,
            correlation_id=get_correlation_id() or None,
        )
        return self._issue_tokens(user)

    def refresh(self, payload: RefreshTokenRequest) -> TokenPairResponse:
        claims = decode_jwt_token(payload.refresh_token, expected_type="refresh")
        user_id = claims.get("sub", "")
        user = self._repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AppException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="USER_INACTIVE_OR_MISSING",
                message="Unable to refresh token for this account.",
            )
        return self._issue_tokens(user)

    def _issue_tokens(self, user) -> TokenPairResponse:
        access_token = create_jwt_token(
            subject=user.id,
            role=user.role,
            token_type="access",
        )
        refresh_token = create_jwt_token(
            subject=user.id,
            role=user.role,
            token_type="refresh",
        )
        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=self._settings.access_token_expire_minutes * 60,
            user=UserService.to_response(user),
        )
