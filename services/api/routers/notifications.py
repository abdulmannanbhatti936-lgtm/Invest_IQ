import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.deps import get_current_user, require_risk_profile
from core.rate_limit import user_rate_limit
from models.notification import Notification
from models.risk_profile import RiskProfile
from models.user import User
from schemas.notification import (
    DeviceOut,
    DeviceRegistration,
    NotificationOut,
    NotificationPage,
    PreferencesOut,
    PreferencesUpdate,
    ReadAllResponse,
)
from services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])

ERRORS = {
    404: {"description": "detail.code: 'notification_not_found' or 'device_not_found'"},
    409: {"description": "detail.code: 'risk_profile_required'"},
    422: {"description": "detail.code: 'quiet_hours_empty' (same start and end time)"},
    429: {"description": "detail.code: 'rate_limited'; Retry-After header in seconds"},
}


def rate_limited_user(
    _: RiskProfile = Depends(require_risk_profile),
    user: User = Depends(get_current_user),
) -> User:
    """Signed in, risk profile done, and within the per-user request limit."""
    wait = user_rate_limit(
        "notifications",
        user.id,
        settings.NOTIFICATIONS_RATE_LIMIT,
        settings.NOTIFICATIONS_RATE_LIMIT_WINDOW_SECONDS,
    )
    if wait:
        raise HTTPException(
            status_code=429,
            detail={"code": "rate_limited", "message": "Too many requests.", "retry_after": wait},
            headers={"Retry-After": str(wait)},
        )
    return user


def _out(row: Notification) -> dict:
    return {
        "id": row.id,
        "type": row.type,
        "rule": row.rule,
        "strength": row.strength,
        "ticker": row.ticker,
        "reasoning": row.reasoning,
        "params": row.params,
        "link": row.link,
        "data_as_of": row.data_as_of,
        "sent_at": row.sent_at,
        "read": row.read,
        "read_at": row.read_at,
    }


def _not_found(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"code": code, "message": message})


@router.get("", response_model=NotificationPage, responses=ERRORS)
def list_notifications(
    before: uuid.UUID | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(rate_limited_user),
    db: Session = Depends(get_db),
):
    """The user's own notifications, newest first, with the unread count (FR34)."""
    result = notification_service.page(db, user, before, limit)
    if result is None:
        raise _not_found("notification_not_found", "Notification not found.")
    rows, next_before, unread = result
    return {"items": [_out(r) for r in rows], "next_before": next_before, "unread_count": unread}


@router.patch("/{notification_id}/read", response_model=NotificationOut, responses=ERRORS)
def mark_read(
    notification_id: uuid.UUID,
    user: User = Depends(rate_limited_user),
    db: Session = Depends(get_db),
):
    row = notification_service.mark_read(db, user, notification_id)
    if row is None:
        raise _not_found("notification_not_found", "Notification not found.")
    return _out(row)


@router.post("/read-all", response_model=ReadAllResponse, responses=ERRORS)
def mark_all_read(user: User = Depends(rate_limited_user), db: Session = Depends(get_db)):
    return {"updated": notification_service.mark_all_read(db, user)}


@router.get("/preferences", response_model=PreferencesOut, responses=ERRORS)
def get_preferences(user: User = Depends(rate_limited_user), db: Session = Depends(get_db)):
    """The user's settings (FR36); a user who never saved any gets every type off."""
    return notification_service.preferences_payload(notification_service.preferences(db, user))


@router.patch("/preferences", response_model=PreferencesOut, responses=ERRORS)
def update_preferences(
    body: PreferencesUpdate,
    user: User = Depends(rate_limited_user),
    db: Session = Depends(get_db),
):
    """Changes only the fields sent; quiet hours are Pakistan time (Asia/Karachi)."""
    try:
        row = notification_service.update_preferences(db, user, body)
    except notification_service.QuietHoursEmpty as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "quiet_hours_empty",
                "message": "Quiet hours need different start and end times.",
            },
        ) from exc
    return notification_service.preferences_payload(row)


@router.post("/devices", response_model=DeviceOut, status_code=201, responses=ERRORS)
def register_device(
    body: DeviceRegistration,
    user: User = Depends(rate_limited_user),
    db: Session = Depends(get_db),
):
    """Registers this browser's push token (web push through FCM)."""
    device = notification_service.register_device(db, user, body.platform, body.token)
    return {"id": device.id, "platform": device.platform, "created_at": device.created_at}


@router.delete("/devices/{device_id}", status_code=204, responses=ERRORS)
def remove_device(
    device_id: uuid.UUID,
    user: User = Depends(rate_limited_user),
    db: Session = Depends(get_db),
):
    if not notification_service.remove_device(db, user, device_id):
        raise _not_found("device_not_found", "Device not found.")
    return Response(status_code=204)
