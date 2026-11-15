from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    booking_id: Optional[str] = None
    recipient_role: str
    recipient_phone: str
    channel: str
    event_type: str
    message_body: str
    whatsapp_url: str
    delivery_status: str
    created_at: datetime
