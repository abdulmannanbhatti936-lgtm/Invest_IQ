"""Notification API shapes (PRD.md FR33-FR36, Phase 7)."""

import datetime
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from schemas.types import UTCDateTime

NotificationType = Literal["buy", "sell", "roll"]
Rule = Literal["roll_suggested", "sell_forecast", "idle_cash"]


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: NotificationType
    rule: Rule
    # None for a suggestion that rests on no forecast (idle cash)
    strength: Literal["strong", "watch"] | None
    ticker: str | None
    # The English reasoning; the app renders `params` with its own en/ur templates
    reasoning: str
    params: dict[str, Any]
    link: str
    data_as_of: datetime.date | None
    sent_at: UTCDateTime
    read: bool
    read_at: UTCDateTime | None


class NotificationPage(BaseModel):
    items: list[NotificationOut]  # newest first
    next_before: uuid.UUID | None
    unread_count: int


class ReadAllResponse(BaseModel):
    updated: int


class PreferencesOut(BaseModel):
    buy_enabled: bool
    sell_enabled: bool
    roll_enabled: bool
    push_enabled: bool
    sensitivity: Literal["all", "strong_only"]
    daily_cap: int
    quiet_hours_enabled: bool
    quiet_start: datetime.time
    quiet_end: datetime.time
    language: Literal["en", "ur"]
    timezone: Literal["Asia/Karachi"] = "Asia/Karachi"
    # Whether this server can send web push at all (Firebase configured)
    push_available: bool


class PreferencesUpdate(BaseModel):
    """Every field is optional; only the ones sent change."""

    buy_enabled: bool | None = None
    sell_enabled: bool | None = None
    roll_enabled: bool | None = None
    push_enabled: bool | None = None
    sensitivity: Literal["all", "strong_only"] | None = None
    daily_cap: int | None = Field(default=None, ge=1, le=10)
    quiet_hours_enabled: bool | None = None
    quiet_start: datetime.time | None = None
    quiet_end: datetime.time | None = None
    language: Literal["en", "ur"] | None = None

    @model_validator(mode="after")
    def whole_minutes(self) -> "PreferencesUpdate":
        for name in ("quiet_start", "quiet_end"):
            value = getattr(self, name)
            if value is not None and (value.second or value.microsecond or value.tzinfo):
                raise ValueError(f"{name} must be a Pakistan time in whole minutes (HH:MM)")
        return self


class DeviceRegistration(BaseModel):
    platform: Literal["web"]
    token: str = Field(min_length=20, max_length=4096)


class DeviceOut(BaseModel):
    id: uuid.UUID
    platform: Literal["web", "expo"]
    created_at: UTCDateTime
