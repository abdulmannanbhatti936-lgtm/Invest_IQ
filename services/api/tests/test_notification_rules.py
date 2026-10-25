"""
Phase 7: the monitoring agent's rules (services/notification_rules.py), one test per case where a
suggestion must fire and where it must not: no change of signal, low confidence, stale data,
type switched off, below the chosen sensitivity, already sent, daily cap and quiet hours.
"""

import datetime

import pytest

from services import notification_rules as rules
from services.notification_rules import PKT, Forecast, Preferences, Suggestion


def _at(day: str, hour: int, minute: int = 0) -> datetime.datetime:
    return datetime.datetime.combine(
        datetime.date.fromisoformat(day), datetime.time(hour, minute), PKT
    )


def _forecasts(*signals: str) -> list[Forecast]:
    """Newest first, an hour apart."""
    newest = _at("2026-10-23", 18, 30)
    return [
        Forecast(f"f{i}", signal, newest - datetime.timedelta(hours=i))
        for i, signal in enumerate(signals)
    ]


# Sell: only on a change to SELL ---------------------------------------------------------


def test_sell_fires_when_the_signal_changes_to_sell():
    start = rules.sell_streak_start(_forecasts("SELL"), baseline_signal="HOLD")
    assert start.id == "f0"


def test_sell_streak_starts_at_the_first_sell_after_the_last_other_signal():
    start = rules.sell_streak_start(_forecasts("SELL", "SELL", "HOLD", "SELL"), "BUY")
    assert start.id == "f1"


def test_sell_does_not_fire_without_a_newer_forecast():
    assert rules.sell_streak_start([], baseline_signal="HOLD") is None


def test_sell_does_not_fire_when_the_latest_forecast_is_not_sell():
    assert rules.sell_streak_start(_forecasts("HOLD", "SELL"), "HOLD") is None


def test_sell_does_not_fire_when_it_was_already_sell_when_the_portfolio_was_made():
    assert rules.sell_streak_start(_forecasts("SELL", "SELL"), baseline_signal="SELL") is None


def test_sell_since_the_portfolio_was_made_counts_when_it_was_not_sell_then():
    start = rules.sell_streak_start(_forecasts("SELL", "SELL"), baseline_signal="HOLD")
    assert start.id == "f1"


# Strength: low confidence never makes a strong suggestion ---------------------------------


@pytest.mark.parametrize("sentiment", ["negative", "neutral", "positive", None])
def test_a_low_confidence_sell_is_never_strong(sentiment):
    assert rules.sell_strength(["no_edge_over_baseline"], sentiment) == "watch"


def test_a_sell_is_strong_only_with_a_confident_forecast_and_negative_news():
    assert rules.sell_strength([], "negative") == "strong"
    assert rules.sell_strength([], "neutral") == "watch"
    assert rules.sell_strength([], None) == "watch"


def test_a_roll_is_strong_only_when_both_forecasts_are_confident_and_current():
    assert rules.roll_strength([], []) == "strong"
    assert rules.roll_strength(["below_threshold"], []) == "watch"
    assert rules.roll_strength([], ["models_disagree"]) == "watch"
    assert rules.roll_strength(None, []) == "watch"  # no current forecast for the holding


# Stale data -------------------------------------------------------------------------------


def test_fresh_forecasts_pass():
    now = _at("2026-10-23", 19)
    assert (
        rules.freshness_problem(_at("2026-10-23", 18, 30), datetime.date(2026, 10, 22), now) is None
    )


def test_no_forecasts_skips_the_run():
    assert rules.freshness_problem(None, None, _at("2026-10-23", 19)) == rules.NO_FORECASTS


def test_forecasts_from_yesterday_skip_the_run():
    now = _at("2026-10-23", 19)
    problem = rules.freshness_problem(_at("2026-10-22", 18, 30), datetime.date(2026, 10, 22), now)
    assert problem == rules.FORECASTS_NOT_MADE_TODAY


def test_today_is_pakistan_time_not_utc():
    # 20:00 UTC on the 22nd is 01:00 on the 23rd in Karachi
    made = datetime.datetime(2026, 10, 22, 20, 0, tzinfo=datetime.timezone.utc)
    now = _at("2026-10-23", 19)
    assert rules.freshness_problem(made, datetime.date(2026, 10, 22), now) is None


def test_a_price_date_more_than_two_trading_days_old_skips_the_run():
    now = _at("2026-10-23", 19)  # Friday
    made = _at("2026-10-23", 18, 30)
    assert rules.freshness_problem(made, datetime.date(2026, 10, 21), now) is None  # 2 days
    assert (
        rules.freshness_problem(made, datetime.date(2026, 10, 20), now) == rules.PRICE_DATE_TOO_OLD
    )


def test_weekends_are_not_trading_days():
    # Friday's close checked on Monday evening is one trading day old
    assert rules.trading_days_between(datetime.date(2026, 10, 23), datetime.date(2026, 10, 26)) == 1
    now = _at("2026-10-26", 19)
    made = _at("2026-10-26", 18, 30)
    assert rules.freshness_problem(made, datetime.date(2026, 10, 22), now) is None


# Quiet hours ------------------------------------------------------------------------------

QUIET = Preferences(quiet_hours_enabled=True)  # 22:00-08:00


@pytest.mark.parametrize(
    ("hour", "minute", "quiet"),
    [(21, 59, False), (22, 0, True), (2, 30, True), (7, 59, True), (8, 0, False), (19, 0, False)],
)
def test_an_overnight_quiet_window(hour, minute, quiet):
    assert rules.in_quiet_hours(QUIET, _at("2026-10-23", hour, minute)) is quiet


def test_a_daytime_quiet_window():
    prefs = Preferences(
        quiet_hours_enabled=True,
        quiet_start=datetime.time(13, 0),
        quiet_end=datetime.time(15, 0),
    )
    assert rules.in_quiet_hours(prefs, _at("2026-10-23", 14))
    assert not rules.in_quiet_hours(prefs, _at("2026-10-23", 16))


def test_quiet_hours_off_never_hold_a_push():
    assert not rules.in_quiet_hours(Preferences(), _at("2026-10-23", 23))


def test_quiet_hours_use_pakistan_time():
    # 18:00 UTC is 23:00 in Karachi
    utc = datetime.datetime(2026, 10, 23, 18, 0, tzinfo=datetime.timezone.utc)
    assert rules.in_quiet_hours(QUIET, utc)


def test_the_push_waits_until_the_quiet_window_ends():
    assert rules.quiet_hours_end(QUIET, _at("2026-10-23", 23)) == _at("2026-10-24", 8)
    assert rules.quiet_hours_end(QUIET, _at("2026-10-24", 2)) == _at("2026-10-24", 8)


# Selection --------------------------------------------------------------------------------


def _s(rule: str, strength: str | None, ticker: str | None = "HBL") -> Suggestion:
    return Suggestion(
        rule=rule,
        strength=strength,
        ticker=ticker,
        dedupe_key=f"{rule}:{ticker}:{strength}",
        link="/portfolio",
        params={},
    )


ALL_ON = Preferences(buy_enabled=True, sell_enabled=True, roll_enabled=True)


def test_nothing_is_stored_for_a_type_that_is_switched_off():
    prefs = Preferences(buy_enabled=True)  # sell and roll off
    result = rules.select(
        [_s("sell_forecast", "watch"), _s("idle_cash", None, None)], prefs, set(), 0
    )
    assert [s.rule for s in result.accepted] == ["idle_cash"]
    assert [(s.rule, reason) for s, reason in result.suppressed] == [
        ("sell_forecast", rules.TYPE_OFF)
    ]


def test_strong_only_drops_watch_suggestions_but_keeps_idle_cash():
    prefs = Preferences(
        buy_enabled=True, sell_enabled=True, roll_enabled=True, sensitivity="strong_only"
    )
    found = [_s("sell_forecast", "watch"), _s("roll_suggested", "strong"), _s("idle_cash", None)]
    result = rules.select(found, prefs, set(), 0)
    assert [s.rule for s in result.accepted] == ["roll_suggested", "idle_cash"]
    assert result.suppressed[0][1] == rules.BELOW_SENSITIVITY


def test_a_suggestion_already_stored_is_not_stored_again_nor_counted_against_the_cap():
    sell = _s("sell_forecast", "watch")
    result = rules.select([sell, _s("idle_cash", None)], ALL_ON, {sell.dedupe_key}, 0)
    assert [s.rule for s in result.accepted] == ["idle_cash"]
    assert result.suppressed == [(sell, rules.ALREADY_SENT)]


def test_the_daily_cap_keeps_roll_then_sell_then_buy_and_strong_before_watch():
    found = [
        _s("idle_cash", None, None),
        _s("sell_forecast", "watch", "OGDC"),
        _s("sell_forecast", "strong", "PPL"),
        _s("roll_suggested", "watch", "HBL"),
    ]
    prefs = Preferences(buy_enabled=True, sell_enabled=True, roll_enabled=True, daily_cap=2)
    result = rules.select(found, prefs, set(), 0)
    assert [(s.rule, s.ticker) for s in result.accepted] == [
        ("roll_suggested", "HBL"),
        ("sell_forecast", "PPL"),
    ]
    assert [(s.ticker, reason) for s, reason in result.suppressed] == [
        ("OGDC", rules.CAP_REACHED),
        (None, rules.CAP_REACHED),
    ]


def test_notifications_already_sent_today_use_up_the_cap():
    prefs = Preferences(sell_enabled=True, daily_cap=3)
    found = [_s("sell_forecast", "watch", t) for t in ("A", "B")]
    assert len(rules.select(found, prefs, set(), stored_today=2).accepted) == 1
    result = rules.select(found, prefs, set(), stored_today=3)
    assert result.accepted == []
    assert {reason for _, reason in result.suppressed} == {rules.CAP_REACHED}
