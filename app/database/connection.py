"""Database connection manager supporting SQLAlchemy (PostgreSQL) and SQLite fallback."""
import sqlite3
import threading
from typing import Generator

from app.config.settings import get_settings

INITIAL_MVP_SERVICES = [
    (
        "PET_BOARDING",
        "Pet Boarding",
        "Overnight stay for your pet at an approved caregiver's home.",
        "PER_NIGHT",
    ),
    (
        "IN_HOME_PET_SITTING",
        "In-Home Pet Sitting",
        "Caregiver stays at the pet parent's home to care for the pet.",
        "PER_NIGHT",
    ),
    (
        "DROP_IN_VISITS",
        "Drop-In Visits",
        "Scheduled home visits for feeding, playtime, and check-ins.",
        "PER_VISIT",
    ),
    (
        "DOG_WALKING",
        "Dog Walking",
        "Scheduled neighborhood walks tailored to your dog's routine.",
        "PER_WALK",
    ),
    (
        "DAY_CARE",
        "Pet Day Care",
        "Daytime supervision, meals, and socialization at the caregiver's home.",
        "PER_DAY",
    ),
]


class DatabaseManager:
    """Provides thread-safe relational persistence for repositories."""

    def __init__(self, sqlite_path: str = ":memory:") -> None:
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(sqlite_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self.init_schema()

    def init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    full_name TEXT NOT NULL,
                    phone TEXT,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('PET_PARENT', 'CAREGIVER', 'ADMIN')),
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS ix_users_role ON users(role);

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT,
                    correlation_id TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_audit_logs_actor ON audit_logs(actor_user_id);
                CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action);

                CREATE TABLE IF NOT EXISTS pets (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    species TEXT NOT NULL,
                    breed TEXT,
                    gender TEXT NOT NULL DEFAULT 'UNKNOWN',
                    date_of_birth TEXT,
                    age_years REAL,
                    weight_kg REAL CHECK (weight_kg IS NULL OR weight_kg > 0),
                    photo_url TEXT,
                    personality TEXT,
                    feeding_instructions TEXT,
                    feeding_schedule_json TEXT,
                    walking_schedule_json TEXT,
                    medication_instructions TEXT,
                    allergies TEXT,
                    behaviour_notes TEXT,
                    special_requirements TEXT,
                    additional_notes TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_pets_owner_id ON pets(owner_id);
                CREATE INDEX IF NOT EXISTS ix_pets_species ON pets(species);

                CREATE TABLE IF NOT EXISTS emergency_contacts (
                    id TEXT PRIMARY KEY,
                    pet_id TEXT NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    email TEXT,
                    is_primary INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_emergency_contacts_pet_id ON emergency_contacts(pet_id);

                CREATE TABLE IF NOT EXISTS veterinarians (
                    id TEXT PRIMARY KEY,
                    pet_id TEXT NOT NULL UNIQUE REFERENCES pets(id) ON DELETE CASCADE,
                    clinic_name TEXT NOT NULL,
                    vet_name TEXT,
                    phone TEXT NOT NULL,
                    address TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_veterinarians_pet_id ON veterinarians(pet_id);

                CREATE TABLE IF NOT EXISTS pet_medical_records (
                    id TEXT PRIMARY KEY,
                    pet_id TEXT NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
                    record_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    administered_date TEXT,
                    expiry_date TEXT,
                    provider_name TEXT,
                    document_url TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_pet_medical_records_pet_id ON pet_medical_records(pet_id);

                CREATE TABLE IF NOT EXISTS caregiver_pet_access (
                    pet_id TEXT NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
                    caregiver_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    booking_id TEXT NOT NULL,
                    PRIMARY KEY (pet_id, caregiver_user_id, booking_id)
                );

                CREATE TABLE IF NOT EXISTS services (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    default_price_unit TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS caregivers (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                    bio TEXT NOT NULL,
                    years_of_experience INTEGER NOT NULL DEFAULT 0,
                    experience_summary TEXT,
                    profile_photo_url TEXT,
                    city TEXT NOT NULL,
                    locality TEXT,
                    latitude REAL,
                    longitude REAL,
                    service_radius_km REAL NOT NULL DEFAULT 5.0,
                    supported_species_json TEXT NOT NULL,
                    max_pet_weight_kg REAL,
                    special_capabilities_json TEXT NOT NULL,
                    boarding_details_json TEXT,
                    verification_status TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (verification_status IN ('PENDING', 'UNDER_REVIEW', 'VERIFIED', 'REJECTED', 'EXPIRED')),
                    rating_average REAL NOT NULL DEFAULT 0.0,
                    review_count INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_caregivers_user_id ON caregivers(user_id);
                CREATE INDEX IF NOT EXISTS ix_caregivers_city ON caregivers(city);
                CREATE INDEX IF NOT EXISTS ix_caregivers_verification_status ON caregivers(verification_status);

                CREATE TABLE IF NOT EXISTS caregiver_services (
                    id TEXT PRIMARY KEY,
                    caregiver_id TEXT NOT NULL REFERENCES caregivers(id) ON DELETE CASCADE,
                    service_type TEXT NOT NULL REFERENCES services(code) ON DELETE RESTRICT,
                    price_inr REAL NOT NULL CHECK (price_inr > 0),
                    price_unit TEXT NOT NULL,
                    duration_minutes INTEGER,
                    description TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (caregiver_id, service_type)
                );
                CREATE INDEX IF NOT EXISTS ix_caregiver_services_caregiver_id ON caregiver_services(caregiver_id);
                CREATE INDEX IF NOT EXISTS ix_caregiver_services_service_type ON caregiver_services(service_type);

                CREATE TABLE IF NOT EXISTS caregiver_verifications (
                    id TEXT PRIMARY KEY,
                    caregiver_id TEXT NOT NULL REFERENCES caregivers(id) ON DELETE CASCADE,
                    category TEXT NOT NULL,
                    document_reference TEXT NOT NULL,
                    notes TEXT,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING', 'UNDER_REVIEW', 'VERIFIED', 'REJECTED', 'EXPIRED')),
                    reviewed_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
                    review_notes TEXT,
                    reviewed_at TEXT,
                    expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_caregiver_verifications_caregiver_id ON caregiver_verifications(caregiver_id);

                CREATE TABLE IF NOT EXISTS availability (
                    id TEXT PRIMARY KEY,
                    caregiver_id TEXT NOT NULL REFERENCES caregivers(id) ON DELETE CASCADE,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    max_capacity INTEGER NOT NULL DEFAULT 1 CHECK (max_capacity >= 1),
                    booked_count INTEGER NOT NULL DEFAULT 0 CHECK (booked_count >= 0),
                    is_available INTEGER NOT NULL DEFAULT 1,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_availability_caregiver_id ON availability(caregiver_id);
                CREATE INDEX IF NOT EXISTS ix_availability_window ON availability(caregiver_id, start_time, end_time);
                """
            )
            self._seed_services()
            self._conn.commit()

    def _seed_services(self) -> None:
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO services (code, name, description, default_price_unit, is_active)
            VALUES (?, ?, ?, ?, 1)
            """,
            INITIAL_MVP_SERVICES,
        )

    def reset(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                DELETE FROM availability;
                DELETE FROM caregiver_verifications;
                DELETE FROM caregiver_services;
                DELETE FROM caregivers;
                DELETE FROM caregiver_pet_access;
                DELETE FROM pet_medical_records;
                DELETE FROM veterinarians;
                DELETE FROM emergency_contacts;
                DELETE FROM pets;
                DELETE FROM audit_logs;
                DELETE FROM users;
                """
            )
            self._seed_services()
            self._conn.commit()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    @property
    def lock(self) -> threading.RLock:
        return self._lock


_db_manager = DatabaseManager(get_settings().sqlite_fallback_path)


def get_db_manager() -> DatabaseManager:
    return _db_manager


def get_db() -> Generator[DatabaseManager, None, None]:
    yield _db_manager
