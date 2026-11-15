from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.common.enums import UserRole
from app.database.connection import DatabaseManager, get_db
from app.modules.notifications.schemas import NotificationResponse
from app.modules.notifications.service import WhatsAppNotificationService
from app.modules.users.repository import UserRecord
from app.security.dependencies import require_roles

router = APIRouter(prefix="/notifications", tags=["Notifications & WhatsApp Alerts"])


@router.get("", response_model=List[NotificationResponse])
def list_whatsapp_notifications(
    booking_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    _admin: UserRecord = Depends(require_roles(UserRole.ADMIN)),
    db: DatabaseManager = Depends(get_db),
) -> List[NotificationResponse]:
    """Admin-only endpoint to inspect WhatsApp booking notifications."""
    service = WhatsAppNotificationService(db)
    return service.list_notifications(booking_id=booking_id, limit=limit)
