from fastapi import APIRouter, Depends, status

from app.database.connection import DatabaseManager, get_db
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenPairResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


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


@router.post("/refresh", response_model=TokenPairResponse)
def refresh_access_token(
    payload: RefreshTokenRequest,
    db: DatabaseManager = Depends(get_db),
) -> TokenPairResponse:
    service = AuthService(db)
    return service.refresh(payload)
