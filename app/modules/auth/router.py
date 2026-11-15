from fastapi import APIRouter, Depends, status

from app.database.connection import DatabaseManager, get_db
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
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication (Email, Google, Okta, Mobile OTP)"])


@router.post("/register", response_model=TokenPairResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: RegisterRequest,
    db: DatabaseManager = Depends(get_db),
) -> TokenPairResponse:
    service = AuthService(db)
    return service.register(payload)


@router.post("/login", response_model=TokenPairResponse)
def login_user(
    payload: LoginRequest,
    db: DatabaseManager = Depends(get_db),
) -> TokenPairResponse:
    service = AuthService(db)
    return service.login(payload)


@router.post("/otp/send", response_model=MobileOtpSendResponse)
def send_mobile_otp(
    payload: MobileOtpSendRequest,
    db: DatabaseManager = Depends(get_db),
) -> MobileOtpSendResponse:
    service = AuthService(db)
    return service.send_mobile_otp(payload)


@router.post("/otp/verify", response_model=TokenPairResponse)
def verify_mobile_otp(
    payload: MobileOtpVerifyRequest,
    db: DatabaseManager = Depends(get_db),
) -> TokenPairResponse:
    service = AuthService(db)
    return service.verify_mobile_otp(payload)


@router.post("/oauth/google", response_model=TokenPairResponse)
def login_with_google_oauth(
    payload: GoogleOAuthLoginRequest,
    db: DatabaseManager = Depends(get_db),
) -> TokenPairResponse:
    service = AuthService(db)
    return service.login_with_google(payload)


@router.post("/oauth/okta", response_model=TokenPairResponse)
def login_with_okta_sso(
    payload: OktaOAuthLoginRequest,
    db: DatabaseManager = Depends(get_db),
) -> TokenPairResponse:
    service = AuthService(db)
    return service.login_with_okta(payload)


@router.post("/refresh", response_model=TokenPairResponse)
def refresh_access_token(
    payload: RefreshTokenRequest,
    db: DatabaseManager = Depends(get_db),
) -> TokenPairResponse:
    service = AuthService(db)
    return service.refresh(payload)
