"""
The monitoring agent's rules (PRD.md FR33-FR36), pure and deterministic. Every figure comes
from the Phase 3-5 engines' stored output; nothing here calculates a new number.

Suggestions (advisory only, never a trade):
    roll   the Phase 5 roll check says `suggested` for a holding (trigger and cost test passed);
           once per portfolio, holding and replacement
    sell   a holding's forecast changed to SELL after the portfolio was made; once per streak
    buy    the portfolio's idle cash was flagged by No Money Hold (FR24); once per portfolio

Strength: `strong` only when the forecasts involved carry no low-confidence reason (and, for a
sell, the news mood is negative); otherwise `watch`. A low-confidence forecast never makes a
strong suggestion on its own. Idle cash rests on no forecast, so it has no strength.

Per user, in this order: types switched off, then (strong only) watch suggestions are dropped,
then ones already stored (a second run adds nothing), then the daily cap keeps the first N by
priority roll > sell > buy, strong before watch; the rest are logged as `cap_reached`.
"""

import datetime
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

PKT = ZoneInfo("Asia/Karachi")

# Stale-data rule (approved 2026-10-25): the newest forecasts must be made today (Pakistan time)
# from a close at most this many trading days old; Yahoo runs about one trading day behind PSX
MAX_PRICE_AGE_TRADING_DAYS = 2

TYPE_OF_RULE = {"roll_suggested": "roll", "sell_forecast": "sell", "idle_cash": "buy"}
TYPE_PRIORITY = {"roll": 0, "sell": 1, "buy": 2}
STRENGTH_PRIORITY = {"strong": 0, "watch": 1, None: 2}

# Why a found suggestion was not stored
TYPE_OFF = "type_off"
BELOW_SENSITIVITY = "below_sensitivity"
ALREADY_SENT = "already_sent"
CAP_REACHED = "cap_reached"

# Why a whole run was skipped
NO_MODEL = "no_model"
NO_FORECASTS = "no_forecasts"
FORECASTS_NOT_MADE_TODAY = "forecasts_not_made_today"
PRICE_DATE_TOO_OLD = "price_date_too_old"
ANOTHER_RUN_IN_PROGRESS = "another_run_in_progress"


@dataclass(frozen=True)
class Suggestion:
    rule: str
    strength: str | None
    ticker: str | None
    dedupe_key: str
    link: str
    params: dict
    data_as_of: datetime.date | None = None

    @property
    def type(self) -> str:
        return TYPE_OF_RULE[self.rule]

    @property
    def priority(self) -> tuple:
        return (TYPE_PRIORITY[self.type], STRENGTH_PRIORITY[self.strength], self.ticker or "")


@dataclass(frozen=True)
class Preferences:
    buy_enabled: bool = False
    sell_enabled: bool = False
    roll_enabled: bool = False
    sensitivity: str = "all"
    daily_cap: int = 3
    quiet_hours_enabled: bool = False
    quiet_start: datetime.time = datetime.time(22, 0)
    quiet_end: datetime.time = datetime.time(8, 0)

    def type_enabled(self, kind: str) -> bool:
        return {"buy": self.buy_enabled, "sell": self.sell_enabled, "roll": self.roll_enabled}[kind]

    @property
    def any_enabled(self) -> bool:
        return self.buy_enabled or self.sell_enabled or self.roll_enabled


@dataclass
class Selection:
    accepted: list[Suggestion] = field(default_factory=list)
    suppressed: list[tuple[Suggestion, str]] = field(default_factory=list)


# Forecast inputs ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Forecast:
    """One stored forecast, as the rules need it."""

    id: str
    signal: str
    generated_at: datetime.datetime


def sell_streak_start(newer: list[Forecast], baseline_signal: str | None) -> Forecast | None:
    """
    The first forecast of the current SELL streak, if the signal changed to SELL after the
    portfolio was made. `newer` holds the forecasts made after the one the portfolio used,
    newest first; `baseline_signal` is the signal the portfolio was built with.
    """
    if not newer or newer[0].signal != "SELL":
        return None
    start = newer[0]
    for forecast in newer[1:]:
        if forecast.signal != "SELL":
            return start
        start = forecast
    # SELL ever since the portfolio was made: a change only if it was not SELL then
    return None if baseline_signal == "SELL" else start


def sell_strength(low_confidence_reasons: list[str], sentiment_label: str | None) -> str:
    return "strong" if not low_confidence_reasons and sentiment_label == "negative" else "watch"


def roll_strength(held_reasons: list[str] | None, replacement_reasons: list[str] | None) -> str:
    """Strong only when both forecasts behind the switch are current and not low-confidence."""
    if held_reasons is None or replacement_reasons is None:
        return "watch"
    return "strong" if not held_reasons and not replacement_reasons else "watch"


# Run-level checks --------------------------------------------------------------------------


def trading_days_between(earlier: datetime.date, later: datetime.date) -> int:
    """Weekdays after `earlier` up to and including `later` (PSX holidays are not known here)."""
    days, day = 0, earlier
    while day < later:
        day += datetime.timedelta(days=1)
        if day.weekday() < 5:
            days += 1
    return days


def freshness_problem(
    newest_generated_at: datetime.datetime | None,
    newest_as_of: datetime.date | None,
    now: datetime.datetime,
) -> str | None:
    if newest_generated_at is None or newest_as_of is None:
        return NO_FORECASTS
    today = now.astimezone(PKT).date()
    if newest_generated_at.astimezone(PKT).date() != today:
        return FORECASTS_NOT_MADE_TODAY
    if trading_days_between(newest_as_of, today) > MAX_PRICE_AGE_TRADING_DAYS:
        return PRICE_DATE_TOO_OLD
    return None


# Quiet hours (Pakistan time) ---------------------------------------------------------------


def in_quiet_hours(prefs: Preferences, now: datetime.datetime) -> bool:
    if not prefs.quiet_hours_enabled or prefs.quiet_start == prefs.quiet_end:
        return False
    local = now.astimezone(PKT).time()
    start, end = prefs.quiet_start, prefs.quiet_end
    # A window such as 22:00-08:00 runs past midnight
    return start <= local < end if start < end else local >= start or local < end


def quiet_hours_end(prefs: Preferences, now: datetime.datetime) -> datetime.datetime:
    """The next moment the quiet window ends, as an aware datetime."""
    local = now.astimezone(PKT)
    end = datetime.datetime.combine(local.date(), prefs.quiet_end, PKT)
    if end <= local:
        end += datetime.timedelta(days=1)
    return end


# Selection ---------------------------------------------------------------------------------


def select(
    suggestions: list[Suggestion],
    prefs: Preferences,
    stored_keys: set[str],
    stored_today: int,
) -> Selection:
    """
    Which suggestions to store for one user. `stored_keys` are the dedupe keys this user
    already has; `stored_today` counts the user's notifications made today (Pakistan time).
    """
    result = Selection()
    room = max(prefs.daily_cap - stored_today, 0)
    for suggestion in sorted(suggestions, key=lambda s: s.priority):
        if not prefs.type_enabled(suggestion.type):
            reason = TYPE_OFF
        elif prefs.sensitivity == "strong_only" and suggestion.strength == "watch":
            reason = BELOW_SENSITIVITY
        elif suggestion.dedupe_key in stored_keys:
            reason = ALREADY_SENT
        elif len(result.accepted) >= room:
            reason = CAP_REACHED
        else:
            result.accepted.append(suggestion)
            continue
        result.suppressed.append((suggestion, reason))
    return result
