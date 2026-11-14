"""RFC 7519 compliant HS256 JWT creation and verification."""
import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import status

from app.config.settings import get_settings
from app.core.exceptions import AppException


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode((encoded + padding).encode("ascii"))


def create_jwt_token(
    subject: str,
    role: str,
    token_type: str = "access",
    expires_delta_seconds: Optional[int] = None,
) -> str:
    settings = get_settings()
    now = int(time.time())
    if expires_delta_seconds is None:
        if token_type == "refresh":
            expires_delta_seconds = settings.refresh_token_expire_days * 86400
        else:
            expires_delta_seconds = settings.access_token_expire_minutes * 60

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta_seconds,
        "jti": str(uuid.uuid4()),
    }

    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")

    signature = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    signature_segment = _b64url_encode(signature)
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def decode_jwt_token(token: str, expected_type: str = "access") -> Dict[str, Any]:
    settings = get_settings()
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed JWT structure.")
        header_segment, payload_segment, signature_segment = parts
        signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
        expected_sig = hmac.new(
            settings.jwt_secret.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()
        actual_sig = _b64url_decode(signature_segment)
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ValueError("Invalid token signature.")

        payload: Dict[str, Any] = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    except Exception:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_TOKEN",
            message="Authentication token is invalid or malformed.",
        )

    now = int(time.time())
    if int(payload.get("exp", 0)) < now:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_EXPIRED",
            message="Authentication token has expired.",
        )

    if payload.get("type") != expected_type:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_TOKEN_TYPE",
            message=f"Expected '{expected_type}' token.",
        )

    return payload
