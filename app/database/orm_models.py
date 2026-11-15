"""SQLAlchemy 2.0 Declarative Models for PostgreSQL & Alembic migrations."""
from datetime import datetime, timezone

try:
    from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        updated_at = Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
        )

    class AuditLogORM(Base):
        __tablename__ = "audit_logs"

        id = Column(String(36), primary_key=True, nullable=False)
        actor_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
        action = Column(String(100), nullable=False, index=True)
        entity_type = Column(String(64), nullable=False)
        entity_id = Column(String(64), nullable=True)
        correlation_id = Column(String(64), nullable=True)
        metadata_json = Column(Text, nullable=True)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

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

    class ServiceCatalogORM(Base):
        __tablename__ = "services"

        code = Column(String(40), primary_key=True, nullable=False)
        name = Column(String(100), nullable=False)
        description = Column(Text, nullable=False)
        default_price_unit = Column(String(30), nullable=False)
        is_active = Column(Boolean, nullable=False, default=True)

    class CaregiverORM(Base):
        __tablename__ = "caregivers"

        id = Column(String(36), primary_key=True, nullable=False)
        user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
        bio = Column(Text, nullable=False)
        years_of_experience = Column(Integer, nullable=False, default=0)
        experience_summary = Column(Text, nullable=True)
        profile_photo_url = Column(String(512), nullable=True)
        city = Column(String(80), nullable=False, index=True)
        locality = Column(String(120), nullable=True)
        latitude = Column(Float, nullable=True)
        longitude = Column(Float, nullable=True)
        service_radius_km = Column(Float, nullable=False, default=5.0)
        supported_species_json = Column(Text, nullable=False)
        max_pet_weight_kg = Column(Float, nullable=True)
        special_capabilities_json = Column(Text, nullable=False)
        boarding_details_json = Column(Text, nullable=True)
        verification_status = Column(String(32), nullable=False, default="PENDING", index=True)
        rating_average = Column(Float, nullable=False, default=0.0)
        review_count = Column(Integer, nullable=False, default=0)
        is_active = Column(Boolean, nullable=False, default=True)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    class CaregiverServiceORM(Base):
        __tablename__ = "caregiver_services"
        __table_args__ = (UniqueConstraint("caregiver_id", "service_type", name="uq_caregiver_service_type"),)

        id = Column(String(36), primary_key=True, nullable=False)
        caregiver_id = Column(String(36), ForeignKey("caregivers.id", ondelete="CASCADE"), nullable=False, index=True)
        service_type = Column(String(40), ForeignKey("services.code", ondelete="RESTRICT"), nullable=False, index=True)
        price_inr = Column(Float, nullable=False)
        price_unit = Column(String(30), nullable=False)
        duration_minutes = Column(Integer, nullable=True)
        description = Column(Text, nullable=True)
        is_active = Column(Boolean, nullable=False, default=True)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    class CaregiverVerificationORM(Base):
        __tablename__ = "caregiver_verifications"

        id = Column(String(36), primary_key=True, nullable=False)
        caregiver_id = Column(String(36), ForeignKey("caregivers.id", ondelete="CASCADE"), nullable=False, index=True)
        category = Column(String(40), nullable=False)
        document_reference = Column(String(512), nullable=False)
        notes = Column(Text, nullable=True)
        status = Column(String(32), nullable=False, default="PENDING")
        reviewed_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
        review_notes = Column(Text, nullable=True)
        reviewed_at = Column(DateTime(timezone=True), nullable=True)
        expires_at = Column(DateTime(timezone=True), nullable=True)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    class AvailabilityORM(Base):
        __tablename__ = "availability"

        id = Column(String(36), primary_key=True, nullable=False)
        caregiver_id = Column(String(36), ForeignKey("caregivers.id", ondelete="CASCADE"), nullable=False, index=True)
        start_time = Column(DateTime(timezone=True), nullable=False)
        end_time = Column(DateTime(timezone=True), nullable=False)
        max_capacity = Column(Integer, nullable=False, default=1)
        booked_count = Column(Integer, nullable=False, default=0)
        is_available = Column(Boolean, nullable=False, default=True)
        notes = Column(String(255), nullable=True)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    class BookingORM(Base):
        __tablename__ = "bookings"

        id = Column(String(36), primary_key=True, nullable=False)
        pet_parent_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
        caregiver_id = Column(String(36), ForeignKey("caregivers.id", ondelete="RESTRICT"), nullable=False, index=True)
        pet_id = Column(String(36), ForeignKey("pets.id", ondelete="RESTRICT"), nullable=False, index=True)
        availability_slot_id = Column(String(36), ForeignKey("availability.id", ondelete="SET NULL"), nullable=True)
        service_type = Column(String(40), ForeignKey("services.code", ondelete="RESTRICT"), nullable=False)
        start_time = Column(DateTime(timezone=True), nullable=False)
        end_time = Column(DateTime(timezone=True), nullable=False)
        status = Column(String(32), nullable=False, default="PAYMENT_PENDING", index=True)
        unit_price_inr = Column(Float, nullable=False)
        price_unit = Column(String(30), nullable=False)
        units_count = Column(Integer, nullable=False, default=1)
        subtotal_inr = Column(Float, nullable=False)
        platform_commission_inr = Column(Float, nullable=False)
        caregiver_payout_inr = Column(Float, nullable=False)
        total_price_inr = Column(Float, nullable=False)
        special_instructions = Column(Text, nullable=True)
        cancellation_reason = Column(Text, nullable=True)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    class BookingItemORM(Base):
        __tablename__ = "booking_items"

        id = Column(String(36), primary_key=True, nullable=False)
        booking_id = Column(String(36), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
        item_type = Column(String(40), nullable=False)
        description = Column(String(255), nullable=False)
        quantity = Column(Integer, nullable=False, default=1)
        unit_amount_inr = Column(Float, nullable=False)
        total_amount_inr = Column(Float, nullable=False)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

except ImportError:  # pragma: no cover
    Base = None
