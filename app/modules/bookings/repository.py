import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.database.connection import DatabaseManager


@dataclass
class BookingRecord:
    id: str
    pet_parent_id: str
    caregiver_id: str
    pet_id: str
    availability_slot_id: Optional[str]
    service_type: str
    start_time: str
    end_time: str
    status: str
    unit_price_inr: float
    price_unit: str
    units_count: int
    subtotal_inr: float
    platform_commission_inr: float
    caregiver_payout_inr: float
    total_price_inr: float
    special_instructions: Optional[str]
    cancellation_reason: Optional[str]
    media_reviewed_by_admin: bool
    admin_review_notes: Optional[str]
    assigned_by_admin_id: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class BookingItemRecord:
    id: str
    booking_id: str
    item_type: str
    description: str
    quantity: int
    unit_amount_inr: float
    total_amount_inr: float
    created_at: str


class BookingRepository:
    """Data access layer for bookings with serialized transaction locking for double-booking prevention."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    @staticmethod
    def _row_to_booking(r) -> BookingRecord:
        keys = r.keys()
        return BookingRecord(
            id=r["id"],
            pet_parent_id=r["pet_parent_id"],
            caregiver_id=r["caregiver_id"],
            pet_id=r["pet_id"],
            availability_slot_id=r["availability_slot_id"],
            service_type=r["service_type"],
            start_time=r["start_time"],
            end_time=r["end_time"],
            status=r["status"],
            unit_price_inr=float(r["unit_price_inr"]),
            price_unit=r["price_unit"],
            units_count=int(r["units_count"]),
            subtotal_inr=float(r["subtotal_inr"]),
            platform_commission_inr=float(r["platform_commission_inr"]),
            caregiver_payout_inr=float(r["caregiver_payout_inr"]),
            total_price_inr=float(r["total_price_inr"]),
            special_instructions=r["special_instructions"],
            cancellation_reason=r["cancellation_reason"],
            media_reviewed_by_admin=bool(r["media_reviewed_by_admin"]) if "media_reviewed_by_admin" in keys else False,
            admin_review_notes=r["admin_review_notes"] if "admin_review_notes" in keys else None,
            assigned_by_admin_id=r["assigned_by_admin_id"] if "assigned_by_admin_id" in keys else None,
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def get_by_id(self, booking_id: str) -> Optional[BookingRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT * FROM bookings WHERE id = ?",
                (booking_id,),
            )
            r = cur.fetchone()
            return self._row_to_booking(r) if r else None

    def list_booking_items(self, booking_id: str) -> List[BookingItemRecord]:
        with self._db.lock:
            cur = self._db.connection.execute(
                "SELECT * FROM booking_items WHERE booking_id = ? ORDER BY created_at ASC",
                (booking_id,),
            )
            return [
                BookingItemRecord(
                    id=r["id"],
                    booking_id=r["booking_id"],
                    item_type=r["item_type"],
                    description=r["description"],
                    quantity=int(r["quantity"]),
                    unit_amount_inr=float(r["unit_amount_inr"]),
                    total_amount_inr=float(r["total_amount_inr"]),
                    created_at=r["created_at"],
                )
                for r in cur.fetchall()
            ]

    def create_booking_atomic(self, fields: Dict[str, Any]) -> Optional[BookingRecord]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        booking_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())

        with self._db.lock:
            slot_cur = self._db.connection.execute(
                """
                SELECT id, max_capacity, booked_count
                FROM availability
                WHERE caregiver_id = ?
                  AND is_available = 1
                  AND booked_count < max_capacity
                  AND start_time <= ?
                  AND end_time >= ?
                ORDER BY start_time ASC
                LIMIT 1
                """,
                (fields["caregiver_id"], fields["start_time"], fields["end_time"]),
            )
            slot = slot_cur.fetchone()
            if slot is None:
                return None

            overlap_cur = self._db.connection.execute(
                """
                SELECT COUNT(*) AS active_overlaps
                FROM bookings
                WHERE caregiver_id = ?
                  AND status IN ('PENDING_CONFIRMATION', 'PAYMENT_PENDING', 'PAID', 'CONFIRMED', 'IN_PROGRESS')
                  AND start_time < ?
                  AND end_time > ?
                """,
                (fields["caregiver_id"], fields["end_time"], fields["start_time"]),
            )
            active_overlaps = int(overlap_cur.fetchone()["active_overlaps"])
            if active_overlaps >= int(slot["max_capacity"]):
                return None

            new_booked_count = int(slot["booked_count"]) + 1
            self._db.connection.execute(
                "UPDATE availability SET booked_count = ?, updated_at = ? WHERE id = ?",
                (new_booked_count, now, slot["id"]),
            )

            self._db.connection.execute(
                """
                INSERT INTO bookings (
                    id, pet_parent_id, caregiver_id, pet_id, availability_slot_id,
                    service_type, start_time, end_time, status,
                    unit_price_inr, price_unit, units_count,
                    subtotal_inr, platform_commission_inr, caregiver_payout_inr,
                    total_price_inr, special_instructions, cancellation_reason,
                    media_reviewed_by_admin, admin_review_notes, assigned_by_admin_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PAYMENT_PENDING', ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, NULL, NULL, ?, ?)
                """,
                (
                    booking_id,
                    fields["pet_parent_id"],
                    fields["caregiver_id"],
                    fields["pet_id"],
                    slot["id"],
                    fields["service_type"],
                    fields["start_time"],
                    fields["end_time"],
                    fields["unit_price_inr"],
                    fields["price_unit"],
                    fields["units_count"],
                    fields["subtotal_inr"],
                    fields["platform_commission_inr"],
                    fields["caregiver_payout_inr"],
                    fields["total_price_inr"],
                    fields.get("special_instructions"),
                    now,
                    now,
                ),
            )

            self._db.connection.execute(
                """
                INSERT INTO booking_items (
                    id, booking_id, item_type, description, quantity,
                    unit_amount_inr, total_amount_inr, created_at
                ) VALUES (?, ?, 'SERVICE_FEE', ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    booking_id,
                    f"{fields['service_type']} ({fields['units_count']} x {fields['price_unit']})",
                    fields["units_count"],
                    fields["unit_price_inr"],
                    fields["subtotal_inr"],
                    now,
                ),
            )

            self._db.connection.execute(
                "INSERT OR IGNORE INTO caregiver_pet_access (pet_id, caregiver_user_id, booking_id) VALUES (?, ?, ?)",
                (fields["pet_id"], fields["caregiver_user_id"], booking_id),
            )

            self._db.connection.commit()

        return self.get_by_id(booking_id)

    def admin_confirm_payment(
        self,
        booking_id: str,
        review_notes: Optional[str],
    ) -> Optional[BookingRecord]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.lock:
            self._db.connection.execute(
                """
                UPDATE bookings
                SET status = 'PAID',
                    media_reviewed_by_admin = 1,
                    admin_review_notes = COALESCE(?, admin_review_notes),
                    updated_at = ?
                WHERE id = ?
                """,
                (review_notes, now, booking_id),
            )
            self._db.connection.commit()
        return self.get_by_id(booking_id)

    def admin_assign_caretaker(
        self,
        booking_id: str,
        new_caregiver_id: str,
        new_caregiver_user_id: str,
        admin_user_id: str,
        assignment_notes: Optional[str],
    ) -> Optional[BookingRecord]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        booking = self.get_by_id(booking_id)
        if booking is None:
            return None

        with self._db.lock:
            # If Admin reassigns to a different caregiver, transfer slot reservation & pet access
            if booking.caregiver_id != new_caregiver_id:
                slot_cur = self._db.connection.execute(
                    """
                    SELECT id, max_capacity, booked_count
                    FROM availability
                    WHERE caregiver_id = ?
                      AND is_available = 1
                      AND booked_count < max_capacity
                      AND start_time <= ?
                      AND end_time >= ?
                    ORDER BY start_time ASC
                    LIMIT 1
                    """,
                    (new_caregiver_id, booking.start_time, booking.end_time),
                )
                new_slot = slot_cur.fetchone()
                if new_slot is None:
                    return None

                if booking.availability_slot_id:
                    self._db.connection.execute(
                        """
                        UPDATE availability
                        SET booked_count = CASE WHEN booked_count > 0 THEN booked_count - 1 ELSE 0 END,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (now, booking.availability_slot_id),
                    )
                self._db.connection.execute(
                    "UPDATE availability SET booked_count = booked_count + 1, updated_at = ? WHERE id = ?",
                    (now, new_slot["id"]),
                )
                self._db.connection.execute(
                    "DELETE FROM caregiver_pet_access WHERE booking_id = ?",
                    (booking_id,),
                )
                self._db.connection.execute(
                    "INSERT OR IGNORE INTO caregiver_pet_access (pet_id, caregiver_user_id, booking_id) VALUES (?, ?, ?)",
                    (booking.pet_id, new_caregiver_user_id, booking_id),
                )
                new_slot_id = new_slot["id"]
            else:
                new_slot_id = booking.availability_slot_id
                self._db.connection.execute(
                    "INSERT OR IGNORE INTO caregiver_pet_access (pet_id, caregiver_user_id, booking_id) VALUES (?, ?, ?)",
                    (booking.pet_id, new_caregiver_user_id, booking_id),
                )

            combined_notes = (
                f"{booking.admin_review_notes} | {assignment_notes}"
                if booking.admin_review_notes and assignment_notes
                else (assignment_notes or booking.admin_review_notes)
            )
            self._db.connection.execute(
                """
                UPDATE bookings
                SET caregiver_id = ?,
                    availability_slot_id = ?,
                    status = 'CONFIRMED',
                    assigned_by_admin_id = ?,
                    admin_review_notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (new_caregiver_id, new_slot_id, admin_user_id, combined_notes, now, booking_id),
            )
            self._db.connection.commit()

        return self.get_by_id(booking_id)

    def transition_status(
        self,
        booking_id: str,
        new_status: str,
        reason: Optional[str] = None,
        release_capacity: bool = False,
        caregiver_user_id: Optional[str] = None,
    ) -> Optional[BookingRecord]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        booking = self.get_by_id(booking_id)
        if booking is None:
            return None

        with self._db.lock:
            self._db.connection.execute(
                """
                UPDATE bookings
                SET status = ?,
                    cancellation_reason = COALESCE(?, cancellation_reason),
                    updated_at = ?
                WHERE id = ?
                """,
                (new_status, reason, now, booking_id),
            )

            if release_capacity and booking.availability_slot_id:
                self._db.connection.execute(
                    """
                    UPDATE availability
                    SET booked_count = CASE WHEN booked_count > 0 THEN booked_count - 1 ELSE 0 END,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (now, booking.availability_slot_id),
                )

            if release_capacity and caregiver_user_id:
                self._db.connection.execute(
                    "DELETE FROM caregiver_pet_access WHERE pet_id = ? AND caregiver_user_id = ? AND booking_id = ?",
                    (booking.pet_id, caregiver_user_id, booking_id),
                )

            self._db.connection.commit()

        return self.get_by_id(booking_id)

    def list_bookings(
        self,
        pet_parent_id: Optional[str] = None,
        caregiver_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[BookingRecord], int]:
        clauses: List[str] = []
        params: List[Any] = []
        if pet_parent_id:
            clauses.append("pet_parent_id = ?")
            params.append(pet_parent_id)
        if caregiver_id:
            clauses.append("caregiver_id = ?")
            params.append(caregiver_id)
        if status_filter:
            clauses.append("status = ?")
            params.append(status_filter)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._db.lock:
            count_cur = self._db.connection.execute(
                f"SELECT COUNT(*) AS cnt FROM bookings {where_sql}",
                tuple(params),
            )
            total = int(count_cur.fetchone()["cnt"])
            cur = self._db.connection.execute(
                f"SELECT * FROM bookings {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                tuple(params + [limit, offset]),
            )
            return [self._row_to_booking(r) for r in cur.fetchall()], total
