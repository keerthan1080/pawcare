import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.database.connection import DatabaseManager


@dataclass
class CaregiverRecord:
    id: str
    user_id: str
    full_name: str
    bio: str
    years_of_experience: int
    experience_summary: Optional[str]
    profile_photo_url: Optional[str]
    city: str
    locality: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    service_radius_km: float
    supported_species_json: str
    max_pet_weight_kg: Optional[float]
    special_capabilities_json: str
    boarding_details_json: Optional[str]
    verification_status: str
    rating_average: float
    review_count: int
    is_active: bool
    created_at: str
    updated_at: str


@dataclass
class CaregiverServiceRecord:
    id: str
    caregiver_id: str
    service_type: str
    price_inr: float
    price_unit: str
    duration_minutes: Optional[int]
    description: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str


@dataclass
class CaregiverVerificationRecord:
    id: str
    caregiver_id: str
    category: str
    document_reference: str
    notes: Optional[str]
    status: str
    reviewed_by_user_id: Optional[str]
    review_notes: Optional[str]
    reviewed_at: Optional[str]
    expires_at: Optional[str]
    created_at: str
    updated_at: str


class CaregiverRepository:
    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    @staticmethod
    def _row_to_caregiver(row) -> CaregiverRecord:
        return CaregiverRecord(
            id=row["id"],
            user_id=row["user_id"],
            full_name=row["full_name"],
            bio=row["bio"],
            years_of_experience=int(row["years_of_experience"]),
            experience_summary=row["experience_summary"],
            profile_photo_url=row["profile_photo_url"],
            city=row["city"],
            locality=row["locality"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            service_radius_km=float(row["service_radius_km"]),
            supported_species_json=row["supported_species_json"],
            max_pet_weight_kg=row["max_pet_weight_kg"],
            special_capabilities_json=row["special_capabilities_json"],
            boarding_details_json=row["boarding_details_json"],
            verification_status=row["verification_status"],
            rating_average=float(row["rating_average"]),
            review_count=int(row["review_count"]),
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_by_id(self, caregiver_id: str) -> Optional[CaregiverRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                """
                SELECT c.*, u.full_name
                FROM caregivers c
                JOIN users u ON u.id = c.user_id
                WHERE c.id = ?
                """,
                (caregiver_id,),
            )
            row = cur.fetchone()
            return self._row_to_caregiver(row) if row else None

    def get_by_user_id(self, user_id: str) -> Optional[CaregiverRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                """
                SELECT c.*, u.full_name
                FROM caregivers c
                JOIN users u ON u.id = c.user_id
                WHERE c.user_id = ?
                """,
                (user_id,),
            )
            row = cur.fetchone()
            return self._row_to_caregiver(row) if row else None

    def create_caregiver(self, user_id: str, fields: Dict[str, Any]) -> CaregiverRecord:
        cg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.lock:
            self._db.connection.execute(
                """
                INSERT INTO caregivers (
                    id, user_id, bio, years_of_experience, experience_summary,
                    profile_photo_url, city, locality, latitude, longitude,
                    service_radius_km, supported_species_json, max_pet_weight_kg,
                    special_capabilities_json, boarding_details_json,
                    verification_status, rating_average, review_count, is_active,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0.0, 0, 1, ?, ?)
                """,
                (
                    cg_id,
                    user_id,
                    fields["bio"],
                    fields.get("years_of_experience", 0),
                    fields.get("experience_summary"),
                    fields.get("profile_photo_url"),
                    fields["city"],
                    fields.get("locality"),
                    fields.get("latitude"),
                    fields.get("longitude"),
                    fields.get("service_radius_km", 5.0),
                    json.dumps(fields["supported_species"]),
                    fields.get("max_pet_weight_kg"),
                    json.dumps(fields.get("special_capabilities", [])),
                    json.dumps(fields["boarding_details"]) if fields.get("boarding_details") else None,
                    now,
                    now,
                ),
            )
            self._db.connection.commit()
        return self.get_by_id(cg_id)  # type: ignore[return-value]

    def update_caregiver(self, caregiver_id: str, updates: Dict[str, Any]) -> Optional[CaregiverRecord]:
        if not updates:
            return self.get_by_id(caregiver_id)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        updates["updated_at"] = now
        set_cols = ", ".join(f"{col} = ?" for col in updates.keys())
        values = list(updates.values()) + [caregiver_id]
        with self._db.lock:
            self._db.connection.execute(
                f"UPDATE caregivers SET {set_cols} WHERE id = ?",
                tuple(values),
            )
            self._db.connection.commit()
        return self.get_by_id(caregiver_id)

    def replace_services(
        self,
        caregiver_id: str,
        services: List[Dict[str, Any]],
    ) -> List[CaregiverServiceRecord]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.lock:
            self._db.connection.execute(
                "DELETE FROM caregiver_services WHERE caregiver_id = ?",
                (caregiver_id,),
            )
            for item in services:
                sid = str(uuid.uuid4())
                self._db.connection.execute(
                    """
                    INSERT INTO caregiver_services (
                        id, caregiver_id, service_type, price_inr, price_unit,
                        duration_minutes, description, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sid,
                        caregiver_id,
                        item["service_type"],
                        float(item["price_inr"]),
                        item["price_unit"],
                        item.get("duration_minutes"),
                        item.get("description"),
                        1 if item.get("is_active", True) else 0,
                        now,
                        now,
                    ),
                )
            self._db.connection.commit()
        return self.list_services(caregiver_id)

    def list_services(self, caregiver_id: str) -> List[CaregiverServiceRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT * FROM caregiver_services WHERE caregiver_id = ? ORDER BY service_type ASC",
                (caregiver_id,),
            )
            return [
                CaregiverServiceRecord(
                    id=r["id"],
                    caregiver_id=r["caregiver_id"],
                    service_type=r["service_type"],
                    price_inr=float(r["price_inr"]),
                    price_unit=r["price_unit"],
                    duration_minutes=r["duration_minutes"],
                    description=r["description"],
                    is_active=bool(r["is_active"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in cur.fetchall()
            ]

    def get_service_for_caregiver(
        self,
        caregiver_id: str,
        service_type: str,
    ) -> Optional[CaregiverServiceRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                """
                SELECT * FROM caregiver_services
                WHERE caregiver_id = ? AND service_type = ? AND is_active = 1
                """,
                (caregiver_id, service_type),
            )
            r = cur.fetchone()
            if not r:
                return None
            return CaregiverServiceRecord(
                id=r["id"],
                caregiver_id=r["caregiver_id"],
                service_type=r["service_type"],
                price_inr=float(r["price_inr"]),
                price_unit=r["price_unit"],
                duration_minutes=r["duration_minutes"],
                description=r["description"],
                is_active=bool(r["is_active"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )

    def create_verification(
        self,
        caregiver_id: str,
        category: str,
        document_reference: str,
        notes: Optional[str],
    ) -> CaregiverVerificationRecord:
        vid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.lock:
            self._db.connection.execute(
                """
                INSERT INTO caregiver_verifications (
                    id, caregiver_id, category, document_reference, notes,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'UNDER_REVIEW', ?, ?)
                """,
                (vid, caregiver_id, category, document_reference, notes, now, now),
            )
            self._db.connection.execute(
                """
                UPDATE caregivers
                SET verification_status = CASE
                    WHEN verification_status = 'PENDING' THEN 'UNDER_REVIEW'
                    ELSE verification_status
                END,
                updated_at = ?
                WHERE id = ?
                """,
                (now, caregiver_id),
            )
            self._db.connection.commit()
        return self.get_verification_by_id(vid)  # type: ignore[return-value]

    def get_verification_by_id(self, verification_id: str) -> Optional[CaregiverVerificationRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT * FROM caregiver_verifications WHERE id = ?",
                (verification_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return CaregiverVerificationRecord(
                id=r["id"],
                caregiver_id=r["caregiver_id"],
                category=r["category"],
                document_reference=r["document_reference"],
                notes=r["notes"],
                status=r["status"],
                reviewed_by_user_id=r["reviewed_by_user_id"],
                review_notes=r["review_notes"],
                reviewed_at=r["reviewed_at"],
                expires_at=r["expires_at"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )

    def list_verifications(self, caregiver_id: str) -> List[CaregiverVerificationRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT * FROM caregiver_verifications WHERE caregiver_id = ? ORDER BY created_at DESC",
                (caregiver_id,),
            )
            return [
                CaregiverVerificationRecord(
                    id=r["id"],
                    caregiver_id=r["caregiver_id"],
                    category=r["category"],
                    document_reference=r["document_reference"],
                    notes=r["notes"],
                    status=r["status"],
                    reviewed_by_user_id=r["reviewed_by_user_id"],
                    review_notes=r["review_notes"],
                    reviewed_at=r["reviewed_at"],
                    expires_at=r["expires_at"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in cur.fetchall()
            ]

    def review_verification_item(
        self,
        verification_id: str,
        reviewer_user_id: str,
        status_val: str,
        review_notes: Optional[str],
        expires_at: Optional[str],
    ) -> Optional[CaregiverVerificationRecord]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.lock:
            self._db.connection.execute(
                """
                UPDATE caregiver_verifications
                SET status = ?, reviewed_by_user_id = ?, review_notes = ?,
                    reviewed_at = ?, expires_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (status_val, reviewer_user_id, review_notes, now, expires_at, now, verification_id),
            )
            self._db.connection.commit()
        return self.get_verification_by_id(verification_id)

    def search_caregivers(
        self,
        city: Optional[str] = None,
        locality: Optional[str] = None,
        service_type: Optional[str] = None,
        species: Optional[str] = None,
        pet_weight_kg: Optional[float] = None,
        verified_only: bool = False,
        min_rating: Optional[float] = None,
        max_price_inr: Optional[float] = None,
        start_iso: Optional[str] = None,
        end_iso: Optional[str] = None,
    ) -> List[CaregiverRecord]:
        clauses = ["c.is_active = 1"]
        params: List[Any] = []

        if city:
            clauses.append("LOWER(c.city) = LOWER(?)")
            params.append(city.strip())

        if locality:
            clauses.append("LOWER(c.locality) = LOWER(?)")
            params.append(locality.strip())

        if verified_only:
            clauses.append("c.verification_status = 'VERIFIED'")

        if min_rating is not None:
            clauses.append("c.rating_average >= ?")
            params.append(float(min_rating))

        if species:
            clauses.append("c.supported_species_json LIKE ?")
            params.append(f'%"{species}"%')

        if pet_weight_kg is not None:
            clauses.append("(c.max_pet_weight_kg IS NULL OR c.max_pet_weight_kg >= ?)")
            params.append(float(pet_weight_kg))

        if service_type or max_price_inr is not None:
            sub_clauses = ["cs.caregiver_id = c.id", "cs.is_active = 1"]
            if service_type:
                sub_clauses.append("cs.service_type = ?")
                params.append(service_type)
            if max_price_inr is not None:
                sub_clauses.append("cs.price_inr <= ?")
                params.append(float(max_price_inr))
            clauses.append(f"EXISTS (SELECT 1 FROM caregiver_services cs WHERE {' AND '.join(sub_clauses)})")

        if start_iso and end_iso:
            clauses.append(
                """
                EXISTS (
                    SELECT 1 FROM availability a
                    WHERE a.caregiver_id = c.id
                      AND a.is_available = 1
                      AND a.booked_count < a.max_capacity
                      AND a.start_time <= ?
                      AND a.end_time >= ?
                )
                """
            )
            params.extend([start_iso, end_iso])

        where_sql = " WHERE " + " AND ".join(clauses)
        with self._db.lock:
            cur = self._db.connection.execute(
                f"""
                SELECT c.*, u.full_name
                FROM caregivers c
                JOIN users u ON u.id = c.user_id
                {where_sql}
                ORDER BY
                    CASE WHEN c.verification_status = 'VERIFIED' THEN 0 ELSE 1 END ASC,
                    c.rating_average DESC,
                    c.years_of_experience DESC
                """,
                tuple(params),
            )
            return [self._row_to_caregiver(r) for r in cur.fetchall()]
