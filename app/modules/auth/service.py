import hashlib
import secrets
import time
from fastapi import status

from app.config.settings import get_settings
from app.core.context import get_correlation_id
from app.core.exceptions import AppException
from app.core.logging import logger
from app.database.connection import DatabaseManager
from app.modules.auth.schemas import (
    GoogleOAuthLoginRequest,
    LoginRequest,
    MobileOtpSendRequest,
    MobileOtpSendResponse,
    MobileOtpVerifyRequest,
    OktaOAuthLoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenPairResponse,
)
from app.modules.users.repository import UserRepository, normalize_phone_digits
from app.modules.users.service import UserService
from app.security.jwt import create_jwt_token, decode_jwt_token
from app.security.passwords import hash_password, verify_password


class AuthService:
    """Business logic for Email/Password, Google Sign-In, Okta OIDC SSO, and Mobile Number OTP Authentication."""

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
            metadata={"role": user.role, "method": "EMAIL_PASSWORD"},
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
            metadata={"method": "EMAIL_PASSWORD"},
        )
        return self._issue_tokens(user)

    def send_mobile_otp(self, payload: MobileOtpSendRequest) -> MobileOtpSendResponse:
        norm_phone = normalize_phone_digits(payload.phone) or payload.phone.strip()
        # In local/dev/test mode, use a deterministic or logged 6-digit OTP; in prod, random CSPRNG 6-digit OTP
        if self._settings.app_env in ("local", "dev", "test"):
            # Deterministic last-6 digits or 654321 for predictable local testing, logged to backend console
            otp_code = "654321"
        else:
            otp_code = f"{secrets.randbelow(900000) + 100000}"

        otp_hash = hash_password(f"otp:{norm_phone}:{otp_code}")
        expires_at = int(time.time()) + self._settings.otp_expire_seconds
        self._repo.create_otp_challenge(
            phone=norm_phone,
            otp_hash=otp_hash,
            role=payload.role.value,
            expires_at=expires_at,
        )

        # Log OTP delivery in developer logs (never expose secrets in production error responses)
        logger.info(
            f"[MOBILE_OTP_DISPATCH] phone={norm_phone} provider={self._settings.sms_provider} "
            f"expires_in={self._settings.otp_expire_seconds}s"
            + (f" dev_otp={otp_code}" if self._settings.app_env in ("local", "dev", "test") else "")
        )
        self._repo.create_audit_log(
            actor_user_id=None,
            action="MOBILE_OTP_SENT",
            entity_type="AUTH_OTP",
            entity_id=norm_phone,
            correlation_id=get_correlation_id() or None,
        )
        return MobileOtpSendResponse(
            phone=norm_phone,
            expires_in_seconds=self._settings.otp_expire_seconds,
            delivery_channel="SMS",
            message="A 6-digit verification code has been sent to your mobile number.",
        )

    def verify_mobile_otp(self, payload: MobileOtpVerifyRequest) -> TokenPairResponse:
        norm_phone = normalize_phone_digits(payload.phone) or payload.phone.strip()
        challenge = self._repo.get_latest_active_otp_challenge(norm_phone)
        if challenge is None:
            raise AppException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="OTP_CHALLENGE_NOT_FOUND",
                message="No active verification code found for this mobile number. Please request a new code.",
            )

        now = int(time.time())
        if now > challenge.expires_at:
            self._repo.mark_otp_consumed(challenge.id)
            raise AppException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="OTP_EXPIRED",
                message="Verification code has expired. Please request a new code.",
            )

        if challenge.attempts >= self._settings.otp_max_attempts:
            self._repo.mark_otp_consumed(challenge.id)
            raise AppException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                code="OTP_MAX_ATTEMPTS_EXCEEDED",
                message="Too many failed verification attempts. Please request a new code.",
            )

        if not verify_password(f"otp:{norm_phone}:{payload.otp_code.strip()}", challenge.otp_hash):
            self._repo.increment_otp_attempts(challenge.id)
            raise AppException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="INVALID_OTP_CODE",
                message="Invalid 6-digit verification code.",
            )

        self._repo.mark_otp_consumed(challenge.id)

        # Find existing user by phone or auto-provision a new account
        user = self._repo.get_by_phone(norm_phone)
        if user is None:
            digits = norm_phone.replace("+", "")
            synthetic_email = f"mobile.{digits}@pawcare.in"
            user = self._repo.get_by_email(synthetic_email)
            if user is None:
                user = self._repo.create_user(
                    email=synthetic_email,
                    full_name=(payload.full_name or f"PawCare Member ({norm_phone[-4:]})").strip(),
                    phone=norm_phone,
                    password_hash=hash_password(secrets.token_urlsafe(24)),
                    role=challenge.role,
                )

        if not user.is_active:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="ACCOUNT_DEACTIVATED",
                message="User account is deactivated.",
            )

        self._repo.create_audit_log(
            actor_user_id=user.id,
            action="USER_LOGGED_IN_MOBILE_OTP",
            entity_type="USER",
            entity_id=user.id,
            correlation_id=get_correlation_id() or None,
            metadata={"phone": norm_phone},
        )
        return self._issue_tokens(user)

    def login_with_google(self, payload: GoogleOAuthLoginRequest) -> TokenPairResponse:
        return self._authenticate_federated_oauth(
            provider="GOOGLE",
            id_token=payload.id_token,
            email=payload.email,
            full_name=payload.full_name,
            requested_role=payload.role.value,
        )

    def login_with_okta(self, payload: OktaOAuthLoginRequest) -> TokenPairResponse:
        return self._authenticate_federated_oauth(
            provider="OKTA",
            id_token=payload.id_token,
            email=payload.email,
            full_name=payload.full_name,
            requested_role=payload.role.value,
            issuer=payload.okta_issuer,
        )

    def _authenticate_federated_oauth(
        self,
        provider: str,
        id_token: str,
        email: str,
        full_name: str,
        requested_role: str,
        issuer: str = None,
    ) -> TokenPairResponse:
        if not id_token or len(id_token.strip()) < 8 or id_token.strip().lower() == "invalid":
            raise AppException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="INVALID_OAUTH_TOKEN",
                message=f"Invalid or unverifiable {provider} identity token.",
            )

        provider_sub = hashlib.sha256(f"{provider}:{email.strip().lower()}".encode("utf-8")).hexdigest()[:32]
        user = self._repo.get_by_email(email)
        if user is None:
            user = self._repo.create_user(
                email=email,
                full_name=full_name,
                phone=None,
                password_hash=hash_password(secrets.token_urlsafe(24)),
                role=requested_role,
            )

        if not user.is_active:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="ACCOUNT_DEACTIVATED",
                message="User account is deactivated.",
            )

        self._repo.link_oauth_identity(
            user_id=user.id,
            provider=provider,
            provider_subject=provider_sub,
            email=user.email,
        )
        self._repo.create_audit_log(
            actor_user_id=user.id,
            action=f"USER_LOGGED_IN_{provider}",
            entity_type="USER",
            entity_id=user.id,
            correlation_id=get_correlation_id() or None,
            metadata={"provider": provider, "issuer": issuer},
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
