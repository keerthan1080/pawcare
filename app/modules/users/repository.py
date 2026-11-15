import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.database.connection import DatabaseManager


def normalize_phone_digits(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    return f"+{digits}" if digits else phone.strip()


@dataclass
class UserRecord:
    id: str
    email: str
    full_name: str
    phone: Optional[str]
    password_hash: str
    role: str
    is_active: bool
    created_at: str
    updated_at: str


@dataclass
class AuditLogRecord:
    id: str
    actor_user_id: Optional[str]
    action: str
    entity_type: str
    entity_id: Optional[str]
    correlation_id: Optional[str]
    metadata_json: Optional[str]
    created_at: str


@dataclass
class MobileOtpChallengeRecord:
    id: str
    phone: str
    otp_hash: str
    role: str
    attempts: int
    is_consumed: bool
    expires_at: int
    created_at: str


class UserRepository:
    """Data access layer for users, OAuth identities, Mobile OTP challenges, and security audit logs."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    @staticmethod
    def _row_to_user(row) -> UserRecord:
        return UserRecord(
            id=row["id"],
            email=row["email"],
            full_name=row["full_name"],
            phone=row["phone"],
            password_hash=row["password_hash"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_by_id(self, user_id: str) -> Optional[UserRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,),
            )
            row = cur.fetchone()
            return self._row_to_user(row) if row else None

    def get_by_email(self, email: str) -> Optional[UserRecord]:
        normalized = email.strip().lower()
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT * FROM users WHERE email = ?",
                (normalized,),
            )
            row = cur.fetchone()
            return self._row_to_user(row) if row else None

    def get_by_phone(self, phone: str) -> Optional[UserRecord]:
        target_norm = normalize_phone_digits(phone)
        if not target_norm:
            return None
        with self._db.lock:
            cur = self._db.connection.execute("SELECT * FROM users WHERE phone IS NOT NULL")
            for row in cur.fetchall():
                if normalize_phone_digits(row["phone"]) == target_norm:
                    return self._row_to_user(row)
            return None

    def create_user(
        self,
        email: str,
        full_name: str,
        phone: Optional[str],
        password_hash: str,
        role: str,
    ) -> UserRecord:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        user_id = str(uuid.uuid4())
        normalized_email = email.strip().lower()
        with self._db.lock:
            self._db.connection.execute(
                """
                INSERT INTO users (id, email, full_name, phone, password_hash, role, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (user_id, normalized_email, full_name.strip(), phone, password_hash, role, now, now),
            )
            self._db.connection.commit()
        return self.get_by_id(user_id)  # type: ignore[return-value]

    def link_oauth_identity(
        self,
        user_id: str,
        provider: str,
        provider_subject: str,
        email: str,
    ) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        oid = str(uuid.uuid4())
        with self._db.lock:
            self._db.connection.execute(
                """
                INSERT OR IGNORE INTO oauth_identities (id, user_id, provider, provider_subject, email, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (oid, user_id, provider.upper(), provider_subject, email.strip().lower(), now),
            )
            self._db.connection.commit()

    def create_otp_challenge(
        self,
        phone: str,
        otp_hash: str,
        role: str,
        expires_at: int,
    ) -> MobileOtpChallengeRecord:
        cid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        norm_phone = normalize_phone_digits(phone) or phone.strip()
        with self._db.lock:
            # Invalidate prior unconsumed challenges for the same phone
            self._db.connection.execute(
                "UPDATE mobile_otp_challenges SET is_consumed = 1 WHERE phone = ? AND is_consumed = 0",
                (norm_phone,),
            )
            self._db.connection.execute(
                """
                INSERT INTO mobile_otp_challenges (id, phone, otp_hash, role, attempts, is_consumed, expires_at, created_at)
                VALUES (?, ?, ?, ?, 0, 0, ?, ?)
                """,
                (cid, norm_phone, otp_hash, role, expires_at, now),
            )
            self._db.connection.commit()
        return MobileOtpChallengeRecord(
            id=cid,
            phone=norm_phone,
            otp_hash=otp_hash,
            role=role,
            attempts=0,
            is_consumed=False,
            expires_at=expires_at,
            created_at=now,
        )

    def get_latest_active_otp_challenge(self, phone: str) -> Optional[MobileOtpChallengeRecord]:
        norm_phone = normalize_phone_digits(phone) or phone.strip()
        with self._db.lock:
            cur = self._db.connection.execute(
                """
                SELECT * FROM mobile_otp_challenges
                WHERE phone = ? AND is_consumed = 0
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (norm_phone,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return MobileOtpChallengeRecord(
                id=r["id"],
                phone=r["phone"],
                otp_hash=r["otp_hash"],
                role=r["role"],
                attempts=int(r["attempts"]),
                is_consumed=bool(r["is_consumed"]),
                expires_at=int(r["expires_at"]),
                created_at=r["created_at"],
            )

    def increment_otp_attempts(self, challenge_id: str) -> int:
        with self._db.lock:
            self._db.connection.execute(
                "UPDATE mobile_otp_challenges SET attempts = attempts + 1 WHERE id = ?",
                (challenge_id,),
            )
            self._db.connection.commit()
            cur = self._db.connection.execute(
                "SELECT attempts FROM mobile_otp_challenges WHERE id = ?",
                (challenge_id,),
            )
            row = cur.fetchone()
            return int(row["attempts"]) if row else 0

    def mark_otp_consumed(self, challenge_id: str) -> None:
        with self._db.lock:
            self._db.connection.execute(
                "UPDATE mobile_otp_challenges SET is_consumed = 1 WHERE id = ?",
                (challenge_id,),
            )
            self._db.connection.commit()

    def update_profile(
        self,
        user_id: str,
        full_name: Optional[str],
        phone: Optional[str],
    ) -> Optional[UserRecord]:
        existing = self.get_by_id(user_id)
        if not existing:
            return None
        new_name = full_name.strip() if full_name is not None else existing.full_name
        new_phone = phone if phone is not None else existing.phone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.lock:
            self._db.connection.execute(
                "UPDATE users SET full_name = ?, phone = ?, updated_at = ? WHERE id = ?",
                (new_name, new_phone, now, user_id),
            )
            self._db.connection.commit()
        return self.get_by_id(user_id)

    def set_active_status(self, user_id: str, is_active: bool) -> Optional[UserRecord]:
        existing = self.get_by_id(user_id)
        if not existing:
            return None
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.lock:
            self._db.connection.execute(
                "UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?",
                (1 if is_active else 0, now, user_id),
            )
            self._db.connection.commit()
        return self.get_by_id(user_id)

    def list_users(
        self,
        offset: int = 0,
        limit: int = 20,
        role: Optional[str] = None,
    ) -> Tuple[List[UserRecord], int]:
        with self._db.lock:
            if role:
                count_cur = self._db.connection.execute(
                    "SELECT COUNT(*) AS cnt FROM users WHERE role = ?",
                    (role,),
                )
                total = int(count_cur.fetchone()["cnt"])
                cur = self._db.connection.execute(
                    "SELECT * FROM users WHERE role = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (role, limit, offset),
                )
            else:
                count_cur = self._db.connection.execute("SELECT COUNT(*) AS cnt FROM users")
                total = int(count_cur.fetchone()["cnt"])
                cur = self._db.connection.execute(
                    "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            items = [self._row_to_user(r) for r in cur.fetchall()]
            return items, total

    def create_audit_log(
        self,
        actor_user_id: Optional[str],
        action: str,
        entity_type: str,
        entity_id: Optional[str],
        correlation_id: Optional[str],
        metadata: Optional[Dict] = None,
    ) -> AuditLogRecord:
        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        metadata_json = json.dumps(metadata) if metadata else None
        with self._db.lock:
            self._db.connection.execute(
                """
                INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id, correlation_id, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (log_id, actor_user_id, action, entity_type, entity_id, correlation_id, metadata_json, now),
            )
            self._db.connection.commit()
        return AuditLogRecord(
            id=log_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            correlation_id=correlation_id,
            metadata_json=metadata_json,
            created_at=now,
        )

    def list_audit_logs(self, limit: int = 50) -> List[AuditLogRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [
                AuditLogRecord(
                    id=r["id"],
                    actor_user_id=r["actor_user_id"],
                    action=r["action"],
                    entity_type=r["entity_type"],
                    entity_id=r["entity_id"],
                    correlation_id=r["correlation_id"],
                    metadata_json=r["metadata_json"],
                    created_at=r["created_at"],
                )
                for r in cur.fetchall()
            ]
