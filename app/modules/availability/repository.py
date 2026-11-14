import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from app.database.connection import DatabaseManager


@dataclass
class AvailabilitySlotRecord:
    id: str
    caregiver_id: str
    start_time: str
    end_time: str
    max_capacity: int
    booked_count: int
    is_available: bool
    notes: Optional[str]
    created_at: str
    updated_at: str


class AvailabilityRepository:
    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    @staticmethod
    def _row_to_slot(r) -> AvailabilitySlotRecord:
        return AvailabilitySlotRecord(
            id=r["id"],
            caregiver_id=r["caregiver_id"],
            start_time=r["start_time"],
            end_time=r["end_time"],
            max_capacity=int(r["max_capacity"]),
            booked_count=int(r["booked_count"]),
            is_available=bool(r["is_available"]),
            notes=r["notes"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def has_overlapping_slot(self, caregiver_id: str, start_iso: str, end_iso: str) -> bool:
        with self._db.lock:
            cur = self._db.connection.execute(
                """
                SELECT 1 FROM availability
                WHERE caregiver_id = ?
                  AND is_available = 1
                  AND start_time < ?
                  AND end_time > ?
                LIMIT 1
                """,
                (caregiver_id, end_iso, start_iso),
            )
            return cur.fetchone() is not None

    def create_slot(
        self,
        caregiver_id: str,
        start_iso: str,
        end_iso: str,
        max_capacity: int,
        notes: Optional[str],
    ) -> AvailabilitySlotRecord:
        slot_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.lock:
            self._db.connection.execute(
                """
                INSERT INTO availability (
                    id, caregiver_id, start_time, end_time, max_capacity,
                    booked_count, is_available, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?, ?)
                """,
                (slot_id, caregiver_id, start_iso, end_iso, max_capacity, notes, now, now),
            )
            self._db.connection.commit()
        return self.get_by_id(slot_id)  # type: ignore[return-value]

    def get_by_id(self, slot_id: str) -> Optional[AvailabilitySlotRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT * FROM availability WHERE id = ?",
                (slot_id,),
            )
            r = cur.fetchone()
            return self._row_to_slot(r) if r else None

    def list_slots_for_caregiver(
        self,
        caregiver_id: str,
        from_iso: Optional[str] = None,
        to_iso: Optional[str] = None,
        only_open: bool = True,
    ) -> List[AvailabilitySlotRecord]:
        clauses = ["caregiver_id = ?"]
        params: List = [caregiver_id]
        if only_open:
            clauses.append("is_available = 1")
            clauses.append("booked_count < max_capacity")
        if from_iso:
            clauses.append("end_time > ?")
            params.append(from_iso)
        if to_iso:
            clauses.append("start_time < ?")
            params.append(to_iso)

        where_sql = " AND ".join(clauses)
        with self._db.lock:
            cur = self._db.connection.execute(
                f"SELECT * FROM availability WHERE {where_sql} ORDER BY start_time ASC",
                tuple(params),
            )
            return [self._row_to_slot(r) for r in cur.fetchall()]

    def delete_slot(self, slot_id: str) -> None:
        with self._db.lock:
            self._db.connection.execute("DELETE FROM availability WHERE id = ?", (slot_id,))
            self._db.connection.commit()
