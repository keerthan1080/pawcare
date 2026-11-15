import os
import re
import urllib.parse
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from app.database.connection import DatabaseManager
from app.modules.notifications.schemas import NotificationResponse


@dataclass
class NotificationRecord:
    id: str
    booking_id: Optional[str]
    recipient_role: str
    recipient_phone: str
    channel: str
    event_type: str
    message_body: str
    whatsapp_url: str
    delivery_status: str
    created_at: str


class WhatsAppNotificationService:
    """Creates and dispatches WhatsApp booking notifications to Admin, Pet Parents, and Caretakers."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self.admin_whatsapp_phone = os.getenv("ADMIN_WHATSAPP_NUMBER", "+91-8247716995")

    @staticmethod
    def build_wa_me_url(phone: str, message: str) -> str:
        digits = re.sub(r"\D", "", phone or "918247716995")
        if len(digits) == 10:
            digits = "91" + digits
        encoded_msg = urllib.parse.quote(message, safe="")
        return f"https://wa.me/{digits}?text={encoded_msg}"

    def send_whatsapp_notification(
        self,
        booking_id: Optional[str],
        recipient_role: str,
        recipient_phone: str,
        event_type: str,
        message_body: str,
    ) -> NotificationRecord:
        nid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        wa_url = self.build_wa_me_url(recipient_phone, message_body)

        with self._db.lock:
            self._db.connection.execute(
                """
                INSERT INTO notifications (
                    id, booking_id, recipient_role, recipient_phone, channel,
                    event_type, message_body, whatsapp_url, delivery_status, created_at
                ) VALUES (?, ?, ?, ?, 'WHATSAPP', ?, ?, ?, 'SENT', ?)
                """,
                (nid, booking_id, recipient_role, recipient_phone, event_type, message_body, wa_url, now),
            )
            self._db.connection.commit()

        return NotificationRecord(
            id=nid,
            booking_id=booking_id,
            recipient_role=recipient_role,
            recipient_phone=recipient_phone,
            channel="WHATSAPP",
            event_type=event_type,
            message_body=message_body,
            whatsapp_url=wa_url,
            delivery_status="SENT",
            created_at=now,
        )

    def list_notifications(self, booking_id: Optional[str] = None, limit: int = 50) -> List[NotificationResponse]:
        with self._db.lock:
            if booking_id:
                cur = self._db.connection.execute(
                    "SELECT * FROM notifications WHERE booking_id = ? ORDER BY created_at DESC LIMIT ?",
                    (booking_id, limit),
                )
            else:
                cur = self._db.connection.execute(
                    "SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            rows = cur.fetchall()
            return [
                NotificationResponse(
                    id=r["id"],
                    booking_id=r["booking_id"],
                    recipient_role=r["recipient_role"],
                    recipient_phone=r["recipient_phone"],
                    channel=r["channel"],
                    event_type=r["event_type"],
                    message_body=r["message_body"],
                    whatsapp_url=r["whatsapp_url"],
                    delivery_status=r["delivery_status"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]
