"""SQLAlchemy 2.0 Declarative Models for PostgreSQL & Alembic migrations."""
from datetime import datetime, timezone

try:
    from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String, Text
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

    class PetORM(Base):
        __tablename__ = "pets"

        id = Column(String(36), primary_key=True, nullable=False)
        owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
        name = Column(String(100), nullable=False)
        species = Column(String(32), nullable=False, index=True)
        breed = Column(String(100), nullable=True)
        gender = Column(String(20), nullable=False, default="UNKNOWN")
        date_of_birth = Column(String(10), nullable=True)
        age_years = Column(Float, nullable=True)
        weight_kg = Column(Float, nullable=True)
        photo_url = Column(String(512), nullable=True)
        personality = Column(Text, nullable=True)
        feeding_instructions = Column(Text, nullable=True)
        feeding_schedule_json = Column(Text, nullable=True)
        walking_schedule_json = Column(Text, nullable=True)
        medication_instructions = Column(Text, nullable=True)
        allergies = Column(Text, nullable=True)
        behaviour_notes = Column(Text, nullable=True)
        special_requirements = Column(Text, nullable=True)
        additional_notes = Column(Text, nullable=True)
        is_active = Column(Boolean, nullable=False, default=True)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    class EmergencyContactORM(Base):
        __tablename__ = "emergency_contacts"

        id = Column(String(36), primary_key=True, nullable=False)
        pet_id = Column(String(36), ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True)
        name = Column(String(120), nullable=False)
        relationship = Column(String(64), nullable=False)
        phone = Column(String(30), nullable=False)
        email = Column(String(255), nullable=True)
        is_primary = Column(Boolean, nullable=False, default=True)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    class VeterinarianORM(Base):
        __tablename__ = "veterinarians"

        id = Column(String(36), primary_key=True, nullable=False)
        pet_id = Column(String(36), ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
        clinic_name = Column(String(150), nullable=False)
        vet_name = Column(String(120), nullable=True)
        phone = Column(String(30), nullable=False)
        address = Column(Text, nullable=True)
        notes = Column(Text, nullable=True)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    class PetMedicalRecordORM(Base):
        __tablename__ = "pet_medical_records"

        id = Column(String(36), primary_key=True, nullable=False)
        pet_id = Column(String(36), ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True)
        record_type = Column(String(32), nullable=False)
        title = Column(String(150), nullable=False)
        administered_date = Column(String(10), nullable=True)
        expiry_date = Column(String(10), nullable=True)
        provider_name = Column(String(150), nullable=True)
        document_url = Column(String(512), nullable=True)
        notes = Column(Text, nullable=True)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

except ImportError:  # pragma: no cover
    Base = None
    UserORM = None
    AuditLogORM = None
    PetORM = None
    EmergencyContactORM = None
    VeterinarianORM = None
    PetMedicalRecordORM = None
