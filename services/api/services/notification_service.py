"""
The notification centre's reads and writes for the API (Phase 7). Every query is filtered by
the signed-in user, so one user's notifications, settings and devices are never reachable from
another account (another user's id answers as "not found").
"""

import datetime
import uuid

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from core.config import settings
from models.notification import Notification, NotificationPreference, PushDevice
from models.user import User
from schemas.notification import PreferencesUpdate


class QuietHoursEmpty(Exception):
    """Quiet hours switched on with the same start and end time."""


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def page(db: Session, user: User, before: uuid.UUID | None, limit: int):
    """Newest first; `before` pages to older ones. None for an unknown `before` cursor."""
    query = db.query(Notification).filter(Notification.user_id == user.id)
    if before is not None:
        cursor = query.filter(Notification.id == before).first()
        if cursor is None:
            return None
        query = query.filter(
            (Notification.sent_at < cursor.sent_at)
            | ((Notification.sent_at == cursor.sent_at) & (Notification.id < cursor.id))
        )
    rows = query.order_by(Notification.sent_at.desc(), Notification.id.desc()).limit(limit + 1)
    rows = rows.all()
    unread = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == user.id, Notification.read.is_(False))
        .scalar()
    )
    next_before = rows[limit - 1].id if len(rows) > limit else None
    return rows[:limit], next_before, unread


def mark_read(db: Session, user: User, notification_id: uuid.UUID) -> Notification | None:
    row = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user.id)
        .first()
    )
    if row is None:
        return None
    if not row.read:
        row.read, row.read_at = True, _now()
        db.commit()
    return row


def mark_all_read(db: Session, user: User) -> int:
    updated = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read.is_(False))
        .update({"read": True, "read_at": _now()}, synchronize_session=False)
    )
    db.commit()
    return updated


def preferences(db: Session, user: User) -> NotificationPreference:
    """The user's settings; a user who never saved any gets the defaults (everything off)."""
    row = db.get(NotificationPreference, user.id)
    if row is None:
        row = NotificationPreference(
            user_id=user.id,
            buy_enabled=False,
            sell_enabled=False,
            roll_enabled=False,
            push_enabled=False,
            sensitivity="all",
            daily_cap=3,
            quiet_hours_enabled=False,
            quiet_start=datetime.time(22, 0),
            quiet_end=datetime.time(8, 0),
            language="en",
        )
    return row


def update_preferences(
    db: Session, user: User, changes: PreferencesUpdate
) -> NotificationPreference:
    row = preferences(db, user)
    for name, value in changes.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, name, value)
    if row.quiet_hours_enabled and row.quiet_start == row.quiet_end:
        raise QuietHoursEmpty()
    db.merge(row)
    db.commit()
    return db.get(NotificationPreference, user.id)


def preferences_payload(row: NotificationPreference) -> dict:
    return {
        "buy_enabled": row.buy_enabled,
        "sell_enabled": row.sell_enabled,
        "roll_enabled": row.roll_enabled,
        "push_enabled": row.push_enabled,
        "sensitivity": row.sensitivity,
        "daily_cap": row.daily_cap,
        "quiet_hours_enabled": row.quiet_hours_enabled,
        "quiet_start": row.quiet_start,
        "quiet_end": row.quiet_end,
        "language": row.language,
        "push_available": settings.push_unavailable_reason() is None,
    }


def register_device(db: Session, user: User, platform: str, token: str) -> PushDevice:
    """A token belongs to one user: registering it from another account moves it there."""
    now = _now()
    stmt = (
        insert(PushDevice)
        .values(
            id=uuid.uuid4(),
            user_id=user.id,
            platform=platform,
            token=token,
            created_at=now,
            last_seen_at=now,
        )
        .on_conflict_do_update(
            constraint="uq_push_devices_token",
            set_={
                "user_id": user.id,
                "platform": platform,
                "last_seen_at": now,
                "revoked_at": None,
            },
        )
        .returning(PushDevice.id)
    )
    device_id = db.execute(stmt).scalar()
    db.commit()
    return db.get(PushDevice, device_id)


def remove_device(db: Session, user: User, device_id: uuid.UUID) -> bool:
    deleted = (
        db.query(PushDevice)
        .filter(PushDevice.id == device_id, PushDevice.user_id == user.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return bool(deleted)
