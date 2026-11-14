import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.database.connection import DatabaseManager


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


class UserRepository:
    """Data access layer for users and security audit logs."""

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
