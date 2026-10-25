"""
Push delivery for stored notifications (Phase 7, Architecture.md §9 `send_notification`). The
in-app list needs nothing more: a notification is delivered there once it is stored. A push
goes to every live device of the user through the channel for its platform; quiet hours hold
it back until they end (`release_quiet_hours`). Latency is from the moment the rule fired to
the push service's answer (FR35, target under 5 s).
"""

import datetime
import logging
import uuid

from sqlalchemy.orm import Session

from integrations.push import PushMessage, channel_for
from models.notification import Notification, NotificationPreference, PushDevice
from services import notification_templates

logger = logging.getLogger(__name__)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _message(notification: Notification, language: str) -> PushMessage:
    title, body = notification_templates.push_text(
        notification.rule, notification.strength, notification.params, language
    )
    return PushMessage(
        title=title,
        body=body,
        link=notification.link,
        tag=f"investiq-{notification.id}",
        data={"notification_id": str(notification.id), "type": notification.type},
    )


def dispatch(db: Session, notification_id: uuid.UUID) -> str:
    """Sends one pending push; returns the notification's push status afterwards."""
    notification = db.get(Notification, notification_id)
    if notification is None or notification.push_status != "pending":
        return notification.push_status if notification else "missing"
    prefs = db.get(NotificationPreference, notification.user_id)
    if prefs is None or not prefs.push_enabled:
        notification.push_status = "off"
        db.commit()
        return notification.push_status

    devices = (
        db.query(PushDevice)
        .filter(PushDevice.user_id == notification.user_id, PushDevice.revoked_at.is_(None))
        .all()
    )
    if not devices:
        notification.push_status = "no_device"
        db.commit()
        return notification.push_status

    message = _message(notification, prefs.language)
    outcomes, delivered = [], False
    for device in devices:
        channel = channel_for(device.platform)
        reason = channel.unavailable_reason() if channel else "no_channel"
        if reason:
            outcomes.append({"device_id": str(device.id), "outcome": reason})
            continue
        sent = channel.send(device.token, message)
        delivered = delivered or sent.delivered
        if sent.token_invalid:
            device.revoked_at = _now()
        outcomes.append(
            {
                "device_id": str(device.id),
                "outcome": "delivered" if sent.delivered else sent.detail or "failed",
            }
        )

    finished = _now()
    notification.push_detail = {"devices": outcomes}
    if delivered:
        notification.push_status = "sent"
        notification.push_sent_at = finished
        # Held back by quiet hours: measured from when it was released, not when it was found
        start = max(notification.detected_at, notification.push_after or notification.detected_at)
        notification.push_latency_ms = round((finished - start).total_seconds() * 1000)
    else:
        notification.push_status = "failed"
        logger.warning("Push for notification %s not delivered: %s", notification.id, outcomes)
    db.commit()
    return notification.push_status


def release_quiet_hours(db: Session, now: datetime.datetime | None = None) -> list[uuid.UUID]:
    """Marks pushes whose quiet hours have ended as pending; returns their ids to dispatch."""
    rows = (
        db.query(Notification)
        .filter(
            Notification.push_status == "waiting_quiet_hours",
            Notification.push_after <= (now or _now()),
        )
        .all()
    )
    for row in rows:
        row.push_status = "pending"
    db.commit()
    return [row.id for row in rows]
