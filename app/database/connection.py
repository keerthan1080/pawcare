"""Database connection manager supporting SQLAlchemy (PostgreSQL) and SQLite fallback."""
import sqlite3
import threading
from typing import Generator

from app.config.settings import get_settings


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
                """
            )
            self._conn.commit()

    def reset(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                DELETE FROM caregiver_pet_access;
                DELETE FROM pet_medical_records;
                DELETE FROM veterinarians;
                DELETE FROM emergency_contacts;
                DELETE FROM pets;
                DELETE FROM audit_logs;
                DELETE FROM users;
                """
            )
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
