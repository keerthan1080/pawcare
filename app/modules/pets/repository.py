import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.database.connection import DatabaseManager


@dataclass
class PetRecord:
    id: str
    owner_id: str
    name: str
    species: str
    breed: Optional[str]
    gender: str
    date_of_birth: Optional[str]
    age_years: Optional[float]
    weight_kg: Optional[float]
    photo_url: Optional[str]
    personality: Optional[str]
    feeding_instructions: Optional[str]
    feeding_schedule_json: Optional[str]
    walking_schedule_json: Optional[str]
    medication_instructions: Optional[str]
    allergies: Optional[str]
    behaviour_notes: Optional[str]
    special_requirements: Optional[str]
    additional_notes: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str


@dataclass
class PetMediaRecord:
    id: str
    pet_id: str
    media_type: str
    title: str
    url: str
    duration_seconds: Optional[int]
    notes: Optional[str]
    created_at: str


@dataclass
class EmergencyContactRecord:
    id: str
    pet_id: str
    name: str
    relationship: str
    phone: str
    email: Optional[str]
    is_primary: bool
    created_at: str
    updated_at: str


@dataclass
class VeterinarianRecord:
    id: str
    pet_id: str
    clinic_name: str
    vet_name: Optional[str]
    phone: str
    address: Optional[str]
    notes: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class MedicalRecord:
    id: str
    pet_id: str
    record_type: str
    title: str
    administered_date: Optional[str]
    expiry_date: Optional[str]
    provider_name: Optional[str]
    document_url: Optional[str]
    notes: Optional[str]
    created_at: str


class PetRepository:
    """Data access layer for pets, media gallery (photos/videos), emergency contacts, vets, and medical records."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    @staticmethod
    def _row_to_pet(row) -> PetRecord:
        return PetRecord(
            id=row["id"],
            owner_id=row["owner_id"],
            name=row["name"],
            species=row["species"],
            breed=row["breed"],
            gender=row["gender"],
            date_of_birth=row["date_of_birth"],
            age_years=row["age_years"],
            weight_kg=row["weight_kg"],
            photo_url=row["photo_url"],
            personality=row["personality"],
            feeding_instructions=row["feeding_instructions"],
            feeding_schedule_json=row["feeding_schedule_json"],
            walking_schedule_json=row["walking_schedule_json"],
            medication_instructions=row["medication_instructions"],
            allergies=row["allergies"],
            behaviour_notes=row["behaviour_notes"],
            special_requirements=row["special_requirements"],
            additional_notes=row["additional_notes"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create_pet(self, owner_id: str, fields: Dict[str, Any]) -> PetRecord:
        pet_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.lock:
            self._db.connection.execute(
                """
                INSERT INTO pets (
                    id, owner_id, name, species, breed, gender, date_of_birth,
                    age_years, weight_kg, photo_url, personality, feeding_instructions,
                    feeding_schedule_json, walking_schedule_json, medication_instructions,
                    allergies, behaviour_notes, special_requirements, additional_notes,
                    is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    pet_id,
                    owner_id,
                    fields["name"],
                    fields["species"],
                    fields.get("breed"),
                    fields.get("gender", "UNKNOWN"),
                    fields.get("date_of_birth"),
                    fields.get("age_years"),
                    fields.get("weight_kg"),
                    fields.get("photo_url"),
                    fields.get("personality"),
                    fields.get("feeding_instructions"),
                    json.dumps(fields.get("feeding_schedule", [])),
                    json.dumps(fields.get("walking_schedule", [])),
                    fields.get("medication_instructions"),
                    fields.get("allergies"),
                    fields.get("behaviour_notes"),
                    fields.get("special_requirements"),
                    fields.get("additional_notes"),
                    now,
                    now,
                ),
            )
            self._db.connection.commit()
        return self.get_by_id(pet_id)  # type: ignore[return-value]

    def get_by_id(self, pet_id: str) -> Optional[PetRecord]:
        with self._db.lock:
            cur = self._db.connection.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
            row = cur.fetchone()
            return self._row_to_pet(row) if row else None

    def list_pets(
        self,
        owner_id: Optional[str] = None,
        species: Optional[str] = None,
        include_inactive: bool = False,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[PetRecord], int]:
        clauses: List[str] = []
        params: List[Any] = []
        if owner_id is not None:
            clauses.append("owner_id = ?")
            params.append(owner_id)
        if species is not None:
            clauses.append("species = ?")
            params.append(species)
        if not include_inactive:
            clauses.append("is_active = 1")

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._db.lock:
            count_cur = self._db.connection.execute(
                f"SELECT COUNT(*) AS cnt FROM pets {where_sql}",
                tuple(params),
            )
            total = int(count_cur.fetchone()["cnt"])
            cur = self._db.connection.execute(
                f"SELECT * FROM pets {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                tuple(params + [limit, offset]),
            )
            return [self._row_to_pet(r) for r in cur.fetchall()], total

    def update_pet(self, pet_id: str, updates: Dict[str, Any]) -> Optional[PetRecord]:
        if not updates:
            return self.get_by_id(pet_id)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        updates["updated_at"] = now
        set_cols = ", ".join(f"{col} = ?" for col in updates.keys())
        values = list(updates.values()) + [pet_id]
        with self._db.lock:
            self._db.connection.execute(
                f"UPDATE pets SET {set_cols} WHERE id = ?",
                tuple(values),
            )
            self._db.connection.commit()
        return self.get_by_id(pet_id)

    def add_pet_media(self, pet_id: str, data: Dict[str, Any]) -> PetMediaRecord:
        mid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.lock:
            self._db.connection.execute(
                """
                INSERT INTO pet_media (id, pet_id, media_type, title, url, duration_seconds, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mid,
                    pet_id,
                    data["media_type"],
                    data["title"].strip(),
                    data["url"].strip(),
                    data.get("duration_seconds"),
                    data.get("notes"),
                    now,
                ),
            )
            self._db.connection.commit()
        return PetMediaRecord(
            id=mid,
            pet_id=pet_id,
            media_type=data["media_type"],
            title=data["title"].strip(),
            url=data["url"].strip(),
            duration_seconds=data.get("duration_seconds"),
            notes=data.get("notes"),
            created_at=now,
        )

    def list_pet_media(self, pet_id: str) -> List[PetMediaRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT * FROM pet_media WHERE pet_id = ? ORDER BY created_at ASC",
                (pet_id,),
            )
            return [
                PetMediaRecord(
                    id=r["id"],
                    pet_id=r["pet_id"],
                    media_type=r["media_type"],
                    title=r["title"],
                    url=r["url"],
                    duration_seconds=r["duration_seconds"],
                    notes=r["notes"],
                    created_at=r["created_at"],
                )
                for r in cur.fetchall()
            ]

    def replace_emergency_contacts(
        self,
        pet_id: str,
        contacts: List[Dict[str, Any]],
    ) -> List[EmergencyContactRecord]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.lock:
            self._db.connection.execute("DELETE FROM emergency_contacts WHERE pet_id = ?", (pet_id,))
            for c in contacts:
                cid = str(uuid.uuid4())
                self._db.connection.execute(
                    """
                    INSERT INTO emergency_contacts (id, pet_id, name, relationship, phone, email, is_primary, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cid,
                        pet_id,
                        c["name"].strip(),
                        c["relationship"].strip(),
                        c["phone"].strip(),
                        c.get("email"),
                        1 if c.get("is_primary", True) else 0,
                        now,
                        now,
                    ),
                )
            self._db.connection.commit()
        return self.list_emergency_contacts(pet_id)

    def list_emergency_contacts(self, pet_id: str) -> List[EmergencyContactRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT * FROM emergency_contacts WHERE pet_id = ? ORDER BY is_primary DESC, created_at ASC",
                (pet_id,),
            )
            return [
                EmergencyContactRecord(
                    id=r["id"],
                    pet_id=r["pet_id"],
                    name=r["name"],
                    relationship=r["relationship"],
                    phone=r["phone"],
                    email=r["email"],
                    is_primary=bool(r["is_primary"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in cur.fetchall()
            ]

    def upsert_veterinarian(
        self,
        pet_id: str,
        vet_data: Optional[Dict[str, Any]],
    ) -> Optional[VeterinarianRecord]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.lock:
            self._db.connection.execute("DELETE FROM veterinarians WHERE pet_id = ?", (pet_id,))
            if vet_data is not None:
                vid = str(uuid.uuid4())
                self._db.connection.execute(
                    """
                    INSERT INTO veterinarians (id, pet_id, clinic_name, vet_name, phone, address, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        vid,
                        pet_id,
                        vet_data["clinic_name"].strip(),
                        vet_data.get("vet_name"),
                        vet_data["phone"].strip(),
                        vet_data.get("address"),
                        vet_data.get("notes"),
                        now,
                        now,
                    ),
                )
            self._db.connection.commit()
        return self.get_veterinarian(pet_id)

    def get_veterinarian(self, pet_id: str) -> Optional[VeterinarianRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT * FROM veterinarians WHERE pet_id = ?",
                (pet_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return VeterinarianRecord(
                id=r["id"],
                pet_id=r["pet_id"],
                clinic_name=r["clinic_name"],
                vet_name=r["vet_name"],
                phone=r["phone"],
                address=r["address"],
                notes=r["notes"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )

    def add_medical_record(self, pet_id: str, data: Dict[str, Any]) -> MedicalRecord:
        mid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.lock:
            self._db.connection.execute(
                """
                INSERT INTO pet_medical_records (
                    id, pet_id, record_type, title, administered_date,
                    expiry_date, provider_name, document_url, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mid,
                    pet_id,
                    data["record_type"],
                    data["title"].strip(),
                    data.get("administered_date"),
                    data.get("expiry_date"),
                    data.get("provider_name"),
                    data.get("document_url"),
                    data.get("notes"),
                    now,
                ),
            )
            self._db.connection.commit()
        return MedicalRecord(
            id=mid,
            pet_id=pet_id,
            record_type=data["record_type"],
            title=data["title"].strip(),
            administered_date=data.get("administered_date"),
            expiry_date=data.get("expiry_date"),
            provider_name=data.get("provider_name"),
            document_url=data.get("document_url"),
            notes=data.get("notes"),
            created_at=now,
        )

    def list_medical_records(self, pet_id: str) -> List[MedicalRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT * FROM pet_medical_records WHERE pet_id = ? ORDER BY created_at DESC",
                (pet_id,),
            )
            return [
                MedicalRecord(
                    id=r["id"],
                    pet_id=r["pet_id"],
                    record_type=r["record_type"],
                    title=r["title"],
                    administered_date=r["administered_date"],
                    expiry_date=r["expiry_date"],
                    provider_name=r["provider_name"],
                    document_url=r["document_url"],
                    notes=r["notes"],
                    created_at=r["created_at"],
                )
                for r in cur.fetchall()
            ]

    def grant_caregiver_pet_access(self, pet_id: str, caregiver_user_id: str, booking_id: str) -> None:
        with self._db.lock:
            self._db.connection.execute(
                "INSERT OR IGNORE INTO caregiver_pet_access (pet_id, caregiver_user_id, booking_id) VALUES (?, ?, ?)",
                (pet_id, caregiver_user_id, booking_id),
            )
            self._db.connection.commit()

    def is_caregiver_authorized_for_pet(self, pet_id: str, caregiver_user_id: str) -> bool:
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT 1 FROM caregiver_pet_access WHERE pet_id = ? AND caregiver_user_id = ? LIMIT 1",
                (pet_id, caregiver_user_id),
            )
            return cur.fetchone() is not None
