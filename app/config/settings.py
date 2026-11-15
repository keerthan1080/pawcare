import os
from functools import lru_cache
from typing import List


class Settings:
    """Environment-driven configuration supporting local, dev, qa, and prod."""

    VALID_ENVIRONMENTS = {"local", "dev", "qa", "prod", "test"}

    def __init__(self) -> None:
        self.app_env: str = os.getenv("APP_ENV", "local").lower()
        if self.app_env not in self.VALID_ENVIRONMENTS:
            raise ValueError(f"Invalid APP_ENV '{self.app_env}'. Expected one of {sorted(self.VALID_ENVIRONMENTS)}.")

        self.app_name: str = os.getenv("APP_NAME", "PawCare")
        self.app_version: str = os.getenv("APP_VERSION", "0.1.0")
        self.debug: bool = os.getenv("DEBUG", "true").lower() in ("1", "true", "yes")
        self.api_v1_prefix: str = os.getenv("API_V1_PREFIX", "/api/v1")

        self.database_url: str = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://pawcare:pawcare_local_dev@localhost:5432/pawcare_db",
        )
        self.sqlite_fallback_path: str = os.getenv("SQLITE_FALLBACK_PATH", ":memory:")
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        self.jwt_secret: str = os.getenv(
            "JWT_SECRET",
            "local-dev-only-secret-key-must-be-overridden-in-prod-32b",
        )
        if self.app_env == "prod" and "local-dev-only" in self.jwt_secret:
            raise RuntimeError("Production environment requires a secure, non-default JWT_SECRET.")

        self.jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
        self.refresh_token_expire_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

        raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost")
        self.cors_origins: List[str] = [o.strip() for o in raw_origins.split(",") if o.strip()]

        # Google Sign-In & Okta SSO Settings
        self.google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
        self.okta_issuer_url: str = os.getenv("OKTA_ISSUER_URL", "")
        self.okta_client_id: str = os.getenv("OKTA_CLIENT_ID", "")

        # Mobile Number OTP Settings
        self.sms_provider: str = os.getenv("SMS_PROVIDER", "local_console")
        self.otp_expire_seconds: int = int(os.getenv("OTP_EXPIRE_SECONDS", "300"))
        self.otp_max_attempts: int = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))


@lru_cache()
def get_settings() -> Settings:
    return Settings()
