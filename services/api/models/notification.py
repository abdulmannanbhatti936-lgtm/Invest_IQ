import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from core.database import Base

NOTIFICATION_TYPES = ("buy", "sell", "roll")
NOTIFICATION_RULES = ("roll_suggested", "sell_forecast", "idle_cash")
STRENGTHS = ("strong", "watch")
PUSH_STATUSES = ("off", "waiting_quiet_hours", "pending", "sent", "no_device", "failed")
PUSH_PLATFORMS = ("web", "expo")
RUN_TRIGGERS = ("schedule", "after_predictions", "cli")
RUN_STATUSES = ("running", "completed", "skipped", "failed")


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class AgentRun(Base):
    """
    One run of the monitoring agent (PRD.md FR33). A skipped run records why (stale forecasts,
    another run in progress), and every suggestion that was found but not sent is listed with
    its reason (type off, below the chosen sensitivity, daily cap reached).
    """

    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(_in("trigger", RUN_TRIGGERS), name="ck_agent_runs_trigger"),
        CheckConstraint(_in("status", RUN_STATUSES), name="ck_agent_runs_status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trigger = Column(String, nullable=False)
    # Set when the run was limited to one user (the run-now command)
    scope_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    started_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False, default="running")
    skip_reason = Column(String, nullable=True)
    model_version = Column(String, nullable=True)
    forecasts_generated_at = Column(DateTime(timezone=True), nullable=True)
    data_as_of = Column(Date, nullable=True)
    portfolios_checked = Column(Integer, nullable=False, default=0)
    notifications_created = Column(Integer, nullable=False, default=0)
    # [{user_id, rule, ticker, reason}] for suggestions found but not stored
    suppressed = Column(JSONB, nullable=False, default=list)
    detail = Column(JSONB, nullable=False, default=dict)


class Notification(Base):
    """
    One suggestion for one user (PRD.md FR34). Advisory only: nothing is ever traded. The
    numbers come from stored data via the Phase 3-5 engines; `params` holds them for the
    app's fixed English and Urdu templates and `reasoning` is the English rendering. The
    unique dedupe key makes a second run of the agent add nothing.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(_in("type", NOTIFICATION_TYPES), name="ck_notifications_type"),
        CheckConstraint(_in("rule", NOTIFICATION_RULES), name="ck_notifications_rule"),
        CheckConstraint(
            f"strength IS NULL OR {_in('strength', STRENGTHS)}", name="ck_notifications_strength"
        ),
        CheckConstraint(_in("push_status", PUSH_STATUSES), name="ck_notifications_push_status"),
        UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
        Index("ix_notifications_user_sent", "user_id", "sent_at"),
        Index("ix_notifications_push_due", "push_status", "push_after"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="SET NULL"))
    agent_run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"))
    type = Column(String, nullable=False)
    rule = Column(String, nullable=False)
    # NULL for a suggestion that does not rest on a forecast (idle cash)
    strength = Column(String, nullable=True)
    ticker = Column(String, nullable=True)
    reasoning = Column(Text, nullable=False)
    params = Column(JSONB, nullable=False)
    link = Column(String, nullable=False)
    data_as_of = Column(Date, nullable=True)
    model_version = Column(String, nullable=True)
    dedupe_key = Column(String, nullable=False)

    detected_at = Column(DateTime(timezone=True), nullable=False)
    # When it reached the in-app list; delivery_latency_ms is detection to that moment
    sent_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    delivery_latency_ms = Column(Integer, nullable=True)
    read = Column(Boolean, nullable=False, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)

    push_status = Column(String, nullable=False, default="off")
    # Quiet hours: the push waits until this moment (the in-app note is there already)
    push_after = Column(DateTime(timezone=True), nullable=True)
    push_sent_at = Column(DateTime(timezone=True), nullable=True)
    push_latency_ms = Column(Integer, nullable=True)
    push_detail = Column(JSONB, nullable=True)


class NotificationPreference(Base):
    """
    Per-user settings (PRD.md FR36). Every type starts off (opt-in). Quiet hours are Pakistan
    time and only hold back the push; the in-app note is still created.
    """

    __tablename__ = "notification_preferences"
    __table_args__ = (
        CheckConstraint(
            "sensitivity IN ('all', 'strong_only')", name="ck_notification_preferences_sensitivity"
        ),
        CheckConstraint("daily_cap BETWEEN 1 AND 10", name="ck_notification_preferences_cap"),
        CheckConstraint("language IN ('en', 'ur')", name="ck_notification_preferences_language"),
    )

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    buy_enabled = Column(Boolean, nullable=False, default=False)
    sell_enabled = Column(Boolean, nullable=False, default=False)
    roll_enabled = Column(Boolean, nullable=False, default=False)
    push_enabled = Column(Boolean, nullable=False, default=False)
    sensitivity = Column(String, nullable=False, default="all")
    daily_cap = Column(Integer, nullable=False, default=3)
    quiet_hours_enabled = Column(Boolean, nullable=False, default=False)
    quiet_start = Column(Time, nullable=False, default=datetime.time(22, 0))
    quiet_end = Column(Time, nullable=False, default=datetime.time(8, 0))
    # Language of the push text (the in-app list follows the app's language)
    language = Column(String, nullable=False, default="en")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class PushDevice(Base):
    """
    A browser (FCM web push, now) or phone (Expo push, Phase 10) that receives pushes. A token
    belongs to one user: registering it again from another account moves it.
    """

    __tablename__ = "push_devices"
    __table_args__ = (
        CheckConstraint(_in("platform", PUSH_PLATFORMS), name="ck_push_devices_platform"),
        UniqueConstraint("token", name="uq_push_devices_token"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform = Column(String, nullable=False)
    token = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    # Set when the push service says the token is no longer valid
    revoked_at = Column(DateTime(timezone=True), nullable=True)
