"""SQLAlchemy 2.0 Declarative Models for PostgreSQL & Alembic migrations.

Note: When running in environments where SQLAlchemy is installed (Docker/PostgreSQL),
these models map directly to PostgreSQL tables and drive Alembic migrations.
"""
from datetime import datetime, timezone

try:
    from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text
    from sqlalchemy.orm import declarative_base

    Base = declarative_base()

    class UserORM(Base):
        __tablename__ = "users"

        id = Column(String(36), primary_key=True, nullable=False)
        email = Column(String(255), unique=True, nullable=False, index=True)
        full_name = Column(String(120), nullable=False)
        phone = Column(String(30), nullable=True)
        password_hash = Column(String(255), nullable=False)
        role = Column(String(32), nullable=False, index=True)
        is_active = Column(Boolean, nullable=False, default=True)
        created_at = Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
        updated_at = Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
        )

    class AuditLogORM(Base):
        __tablename__ = "audit_logs"

        id = Column(String(36), primary_key=True, nullable=False)
        actor_user_id = Column(
            String(36),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        )
        action = Column(String(100), nullable=False, index=True)
        entity_type = Column(String(64), nullable=False)
        entity_id = Column(String(64), nullable=True)
        correlation_id = Column(String(64), nullable=True)
        metadata_json = Column(Text, nullable=True)
        created_at = Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )

except ImportError:  # pragma: no cover - fallback when SQLAlchemy is not installed in test VM
    Base = None
    UserORM = None
    AuditLogORM = None
