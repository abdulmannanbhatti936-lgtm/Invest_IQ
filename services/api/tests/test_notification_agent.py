"""
Phase 7: the monitoring agent end to end on the labelled MOCK market (tests/e2e_market.py, none of
it PSX data): a real portfolio from POST /portfolio/generate, a newer MOCK forecast that changes a
holding to SELL, then the agent and its Celery tasks. Covers: opt-in, the figures coming from the
cost engine, running twice, stale data, the daily cap, sensitivity, quiet hours, push delivery
through a channel, the run lock and the run-now command.
"""

import datetime
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from core.config import settings
from core.database import engine
from integrations import push
from integrations.push import PushResult
from models.notification import AgentRun, Notification, NotificationPreference, PushDevice
from models.portfolio import Portfolio
from models.prediction import Prediction
from models.risk_profile import RiskCategory, RiskProfile
from models.user import User
from services import cost_engine, notification_agent, notification_dispatch, notification_rules
from services.cost_engine import FilerStatus
from tests.conftest import register_and_login
from tests.e2e_market import (
    E2E_MODEL_DIR,
    E2E_MODEL_VERSION,
    E2E_TICKERS,
    LAST_DAY,
    PKT,
    seed_market,
)
from worker import tasks

# The evening after the MOCK market's last close
EVENING = datetime.datetime.combine(LAST_DAY, datetime.time(19, 0), PKT)


@pytest.fixture
def market(db, monkeypatch, fake_redis):
    monkeypatch.setattr(settings, "MODEL_DIR", str(E2E_MODEL_DIR))
    monkeypatch.setattr(settings, "TRACKED_TICKERS", ",".join(E2E_TICKERS))
    seed_market(db)


@pytest.fixture
def investor(client, db, market):
    """A user with a Moderate profile and a real portfolio generated from the MOCK market."""
    headers = register_and_login(client)
    email = client.get("/users/me", headers=headers).json()["email"]
    user = db.query(User).filter(User.email == email).one()
    db.add(RiskProfile(user_id=user.id, category=RiskCategory.moderate, answers={}))
    db.commit()
    response = client.post(
        "/portfolio/generate",
        json={"capital": "100000", "filer_status": "filer"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return {"user": user, "headers": headers, "portfolio_id": uuid.UUID(response.json()["id"])}


def _prefs(db, user, **values):
    row = NotificationPreference(user_id=user.id, **values)
    db.merge(row)
    db.commit()


def _portfolio(db, investor) -> Portfolio:
    return db.get(Portfolio, investor["portfolio_id"])


def _sell_forecast(db, ticker: str, minutes_after: int = 15, signal: str = "SELL") -> Prediction:
    """A newer MOCK forecast for a held stock, made after the portfolio's own forecast."""
    stock_id = db.execute(
        text("SELECT id FROM stocks WHERE ticker = :t"), {"t": ticker}
    ).scalar_one()
    used = (
        db.query(Prediction)
        .filter(Prediction.stock_id == stock_id)
        .order_by(Prediction.generated_at.desc())
        .first()
    )
    prediction = Prediction(
        stock_id=stock_id,
        model_version=E2E_MODEL_VERSION,
        forecast_price=Decimal(used.last_close) * Decimal("0.99"),
        last_close=used.last_close,
        confidence_score=Decimal("0.5"),
        signal=signal,
        signal_probability=Decimal("0.55"),
        as_of_date=LAST_DAY,
        generated_at=used.generated_at + datetime.timedelta(minutes=minutes_after),
    )
    db.add(prediction)
    db.commit()
    return prediction


def _held(db, investor) -> list[str]:
    return [h.stock.ticker for h in _portfolio(db, investor).holdings]


def _run(db, now=EVENING, scope=None, dispatched=None):
    sent = dispatched if dispatched is not None else []
    return notification_agent.run(db, "schedule", sent.append, scope_user_id=scope, now=now)


def _notes(db, user) -> list[Notification]:
    db.expire_all()
    return db.query(Notification).filter(Notification.user_id == user.id).all()


# Opt-in --------------------------------------------------------------------------------------


def test_nothing_is_sent_to_a_user_who_has_not_opted_in(db, investor):
    _sell_forecast(db, _held(db, investor)[0])
    result = _run(db)
    assert result.status == "completed"
    assert _notes(db, investor["user"]) == []
    assert db.get(AgentRun, result.run_id).portfolios_checked == 0


def test_a_sell_change_creates_one_notification_with_cost_engine_figures(db, investor):
    _prefs(db, investor["user"], sell_enabled=True)
    ticker = _held(db, investor)[0]
    _sell_forecast(db, ticker)

    result = _run(db)

    [note] = _notes(db, investor["user"])
    assert result.created == [note.id]
    assert (note.type, note.rule, note.ticker, note.link) == (
        "sell",
        "sell_forecast",
        ticker,
        f"/stocks/{ticker}",
    )
    # Every forecast in the MOCK market is low-confidence (0.5 < 0.6): never a strong suggestion
    assert note.strength == "watch"
    assert "below_threshold" in note.params["low_confidence_reasons"]
    assert note.params["from_signal"] == "HOLD"
    assert note.data_as_of == LAST_DAY
    assert note.read is False and note.push_status == "off"
    assert note.delivery_latency_ms is not None and note.delivery_latency_ms < 5000

    holding = next(h for h in _portfolio(db, investor).holdings if h.stock.ticker == ticker)
    portfolio = _portfolio(db, investor)
    sale = cost_engine.sell(
        holding.shares,
        Decimal(note.params["price"]),
        Decimal(holding.total_cost),
        FilerStatus(portfolio.filer_status),
        cost_engine.load_rates(),
        Decimal(portfolio.commission_rate),
    )
    assert note.params["sale"]["net_proceeds"] == str(sale.net_proceeds)
    assert note.params["sale"]["cgt"] == str(sale.cgt)
    assert note.params["sale"]["charges_total"] == str(sale.charges.total)
    assert f"Rs. {sale.net_proceeds:,.2f}" in note.reasoning
    assert note.reasoning.startswith(f"The latest forecast for {ticker}")


def test_the_agent_never_changes_the_portfolio(db, investor):
    _prefs(db, investor["user"], sell_enabled=True, buy_enabled=True, roll_enabled=True)
    _sell_forecast(db, _held(db, investor)[0])
    before = _portfolio(db, investor)
    snapshot = (
        before.status,
        before.cost_total,
        [(h.shares, h.total_cost) for h in before.holdings],
    )
    _run(db)
    db.expire_all()
    after = _portfolio(db, investor)
    assert (after.status, after.cost_total, [(h.shares, h.total_cost) for h in after.holdings]) == (
        snapshot
    )


# Idempotency -------------------------------------------------------------------------------


def test_running_twice_adds_nothing(db, investor):
    _prefs(db, investor["user"], sell_enabled=True)
    _sell_forecast(db, _held(db, investor)[0])

    first, second = _run(db), _run(db)

    assert len(first.created) == 1 and second.created == []
    assert len(_notes(db, investor["user"])) == 1
    assert {entry["reason"] for entry in second.suppressed} == {notification_rules.ALREADY_SENT}


def test_a_sell_that_stays_sell_is_not_repeated_but_a_new_streak_is(db, investor):
    _prefs(db, investor["user"], sell_enabled=True, daily_cap=10)
    ticker = _held(db, investor)[0]
    _sell_forecast(db, ticker, 10)
    _run(db)
    _sell_forecast(db, ticker, 20)  # still SELL: same streak
    assert _run(db).created == []
    _sell_forecast(db, ticker, 30, signal="HOLD")
    _sell_forecast(db, ticker, 40)  # back to SELL: a new streak
    assert len(_run(db).created) == 1
    assert len(_notes(db, investor["user"])) == 2


# Stale data --------------------------------------------------------------------------------


def test_forecasts_not_made_today_skip_the_run_with_the_reason_stored(db, investor):
    _prefs(db, investor["user"], sell_enabled=True)
    _sell_forecast(db, _held(db, investor)[0])
    result = _run(db, now=EVENING + datetime.timedelta(days=1))
    assert (result.status, result.skip_reason) == ("skipped", "forecasts_not_made_today")
    run = db.get(AgentRun, result.run_id)
    assert (run.status, run.skip_reason, run.data_as_of) == (
        "skipped",
        "forecasts_not_made_today",
        LAST_DAY,
    )
    assert _notes(db, investor["user"]) == []


def test_a_price_date_more_than_two_trading_days_old_skips_the_run(db, investor):
    _prefs(db, investor["user"], sell_enabled=True)
    ticker = _held(db, investor)[0]
    # Made "today", the Wednesday after the MOCK market's last close (a Friday): 3 trading days
    prediction = _sell_forecast(db, ticker)
    later = EVENING + datetime.timedelta(days=5)
    prediction.generated_at = later - datetime.timedelta(minutes=30)
    db.commit()
    result = _run(db, now=later)
    assert result.skip_reason == "price_date_too_old"
    assert _notes(db, investor["user"]) == []


def test_no_model_skips_the_run(db, investor, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MODEL_DIR", str(tmp_path))
    assert _run(db).skip_reason == "no_model"


# Preferences -------------------------------------------------------------------------------


def test_a_type_switched_off_is_logged_not_stored(db, investor):
    _prefs(db, investor["user"], buy_enabled=True, roll_enabled=True)  # sell off
    _sell_forecast(db, _held(db, investor)[0])
    result = _run(db)
    assert not any(n.rule == "sell_forecast" for n in _notes(db, investor["user"]))
    assert {"rule": "sell_forecast", "reason": "type_off"}.items() <= next(
        e for e in result.suppressed if e["rule"] == "sell_forecast"
    ).items()


def test_strong_only_drops_a_low_confidence_sell(db, investor):
    _prefs(db, investor["user"], sell_enabled=True, sensitivity="strong_only")
    _sell_forecast(db, _held(db, investor)[0])
    result = _run(db)
    assert _notes(db, investor["user"]) == []
    assert [e["reason"] for e in result.suppressed] == ["below_sensitivity"]


def test_the_daily_cap_keeps_the_first_and_logs_the_rest(db, investor, caplog):
    _prefs(db, investor["user"], sell_enabled=True, daily_cap=1)
    first, second = sorted(_held(db, investor))[:2]
    _sell_forecast(db, first)
    _sell_forecast(db, second)

    with caplog.at_level("INFO", logger="services.notification_agent"):
        result = _run(db)

    [note] = _notes(db, investor["user"])
    assert note.ticker == first  # same priority: alphabetical, so the order is stable
    assert [e["ticker"] for e in result.suppressed if e["reason"] == "cap_reached"] == [second]
    assert "cap reached" in caplog.text
    assert db.get(AgentRun, result.run_id).suppressed == result.suppressed


# Push --------------------------------------------------------------------------------------


class FakeChannel:
    platform = "web"

    def __init__(self, result=PushResult(True)):
        self.result = result
        self.sent = []

    def unavailable_reason(self):
        return None

    def send(self, token, message):
        self.sent.append((token, message))
        return self.result


@pytest.fixture
def channel(monkeypatch):
    fake = FakeChannel()
    monkeypatch.setitem(push.CHANNELS, "web", fake)
    return fake


def _device(db, user, token="fcm-token-0123456789abcdef"):
    device = PushDevice(user_id=user.id, platform="web", token=token)
    db.add(device)
    db.commit()
    return device


def test_a_push_is_queued_then_delivered_with_its_latency(db, investor, channel):
    _prefs(db, investor["user"], sell_enabled=True, push_enabled=True, language="ur")
    _device(db, investor["user"])
    ticker = _held(db, investor)[0]
    _sell_forecast(db, ticker)
    queued = []

    _run(db, dispatched=queued)

    [note] = _notes(db, investor["user"])
    assert queued == [note.id] and note.push_status == "pending"
    assert notification_dispatch.dispatch(db, note.id) == "sent"
    db.refresh(note)
    assert note.push_sent_at is not None and note.push_latency_ms is not None
    [(token, message)] = channel.sent
    assert token == "fcm-token-0123456789abcdef"
    # Urdu text, the deep link, and no rupee figure in the push itself (Design.md §19)
    assert message.title == f"{ticker} کی فروخت پر غور کریں"
    assert message.link == f"/stocks/{ticker}"
    assert "Rs." not in message.body and "Rs." not in message.title
    # Delivered once: dispatching again sends nothing
    assert notification_dispatch.dispatch(db, note.id) == "sent"
    assert len(channel.sent) == 1


def test_a_dead_token_is_revoked(db, investor, monkeypatch):
    monkeypatch.setitem(
        push.CHANNELS, "web", FakeChannel(PushResult(False, token_invalid=True, detail="gone"))
    )
    _prefs(db, investor["user"], sell_enabled=True, push_enabled=True)
    device = _device(db, investor["user"])
    _sell_forecast(db, _held(db, investor)[0])
    _run(db)
    [note] = _notes(db, investor["user"])
    assert notification_dispatch.dispatch(db, note.id) == "failed"
    db.refresh(device)
    assert device.revoked_at is not None


def test_push_with_no_device_is_recorded(db, investor):
    _prefs(db, investor["user"], sell_enabled=True, push_enabled=True)
    _sell_forecast(db, _held(db, investor)[0])
    _run(db)
    [note] = _notes(db, investor["user"])
    assert notification_dispatch.dispatch(db, note.id) == "no_device"


def test_quiet_hours_hold_the_push_but_not_the_note(db, investor, channel):
    _prefs(
        db,
        investor["user"],
        sell_enabled=True,
        push_enabled=True,
        quiet_hours_enabled=True,
        quiet_start=datetime.time(18, 0),
        quiet_end=datetime.time(21, 0),
    )
    _device(db, investor["user"])
    _sell_forecast(db, _held(db, investor)[0])
    queued = []

    _run(db, dispatched=queued)

    [note] = _notes(db, investor["user"])
    assert queued == []  # nothing pushed during quiet hours
    assert note.push_status == "waiting_quiet_hours"
    end = datetime.datetime.combine(LAST_DAY, datetime.time(21, 0), PKT)
    assert note.push_after == end
    assert notification_dispatch.release_quiet_hours(db, end - datetime.timedelta(minutes=1)) == []
    assert notification_dispatch.release_quiet_hours(db, end) == [note.id]
    assert notification_dispatch.dispatch(db, note.id) == "sent"
    assert len(channel.sent) == 1


def test_a_push_channel_that_is_not_configured_leaves_the_note(db, investor):
    # The real FCM channel without FIREBASE_SERVICE_ACCOUNT_FILE: no network call is made
    _prefs(db, investor["user"], sell_enabled=True, push_enabled=True)
    _device(db, investor["user"])
    _sell_forecast(db, _held(db, investor)[0])
    _run(db)
    [note] = _notes(db, investor["user"])
    assert notification_dispatch.dispatch(db, note.id) == "failed"
    db.refresh(note)
    assert note.push_detail["devices"][0]["outcome"] == "not_configured"


# Roll and idle cash ------------------------------------------------------------------------


def test_a_suggested_roll_becomes_a_roll_notification(db, investor, monkeypatch):
    ticker = _held(db, investor)[0]

    def suggested(_db, portfolio, universe=None):
        return {
            "holdings": [
                {
                    "ticker": ticker,
                    "status": "suggested",
                    "trading_days": 21,
                    "holding_return_pct": "-12.00",
                    "benchmark_return_pct": "1.00",
                    "relative_return_pct": "-13.00",
                    "threshold_pct": "8.00",
                    "replacement": {
                        "ticker": "MOCKX",
                        "price": "50.00",
                        "expected_change_pct": "2",
                    },
                    "sale": {"net_proceeds": "15000.00"},
                    "purchase": {"shares": 299},
                    "switch_cost": "60.00",
                    "expected_benefit": "300.00",
                }
            ]
        }

    monkeypatch.setattr(notification_agent, "roll_check", suggested)
    _prefs(db, investor["user"], roll_enabled=True)
    _run(db)
    [note] = _notes(db, investor["user"])
    assert (note.type, note.rule, note.link, note.strength) == (
        "roll",
        "roll_suggested",
        "/portfolio",
        "watch",
    )
    assert note.dedupe_key == f"roll:{investor['portfolio_id']}:{ticker}:MOCKX"
    assert "expected gain Rs. 300.00, cost of switching Rs. 60.00" in note.reasoning


def test_flagged_idle_cash_becomes_one_buy_notification(db, investor):
    portfolio = _portfolio(db, investor)
    portfolio.input_snapshot = {
        **portfolio.input_snapshot,
        "idle": {"flagged": True, "blocked_by": {"MOCKE2EA": "stock_cap"}},
    }
    db.commit()
    _prefs(db, investor["user"], buy_enabled=True)
    _run(db)
    _run(db)
    [note] = _notes(db, investor["user"])
    assert (note.type, note.rule, note.strength) == ("buy", "idle_cash", None)
    assert note.params["amount"] == str(portfolio.idle_cash)


# Lock, tasks, command ----------------------------------------------------------------------


def test_a_second_run_while_one_holds_the_lock_is_skipped(db, investor):
    other = engine.connect()
    try:
        other.execute(text("SELECT pg_advisory_lock(:k)"), {"k": notification_agent.AGENT_LOCK_KEY})
        result = _run(db)
        assert result.skip_reason == "another_run_in_progress"
    finally:
        other.execute(
            text("SELECT pg_advisory_unlock(:k)"), {"k": notification_agent.AGENT_LOCK_KEY}
        )
        other.commit()
        other.close()


def test_the_celery_task_twice_stores_one_notification_and_queues_one_push(
    db, investor, monkeypatch, queued_tasks
):
    _prefs(db, investor["user"], sell_enabled=True, push_enabled=True)
    _sell_forecast(db, _held(db, investor)[0])
    real_run = notification_agent.run
    monkeypatch.setattr(
        notification_agent,
        "run",
        lambda session, trigger, dispatch, **kw: real_run(session, trigger, dispatch, now=EVENING),
    )

    first = tasks.monitor_portfolios(trigger="schedule")
    second = tasks.monitor_portfolios(trigger="schedule")

    assert (first["created"], second["created"]) == (1, 0)
    [note] = _notes(db, investor["user"])
    assert queued_tasks.named("send_notification") == [((str(note.id),), {})]
    assert tasks.send_notification(str(note.id)) == {"push_status": "no_device"}


def test_forecasts_finishing_start_the_agent(queued_tasks, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MODEL_DIR", str(tmp_path))
    tasks._start_agent()
    assert queued_tasks.named("monitor_portfolios") == [
        ((), {"kwargs": {"trigger": "after_predictions"}})
    ]


def test_run_now_command_for_unknown_and_portfolio_less_accounts(db, client, capsys):
    assert notification_agent._run_now("nobody@example.com") == 1
    assert "No account" in capsys.readouterr().out
    headers = register_and_login(client)
    email = client.get("/users/me", headers=headers).json()["email"]
    assert notification_agent._run_now(email) == 1
    assert "no active portfolio" in capsys.readouterr().out


def test_run_now_uses_the_same_rules_for_one_user(db, investor, client, monkeypatch, capsys):
    _prefs(db, investor["user"], sell_enabled=True)
    _sell_forecast(db, _held(db, investor)[0])
    real_run = notification_agent.run
    monkeypatch.setattr(
        notification_agent,
        "run",
        lambda session, trigger, dispatch, **kw: real_run(
            session, trigger, dispatch, now=EVENING, **kw
        ),
    )
    email = client.get("/users/me", headers=investor["headers"]).json()["email"]

    assert notification_agent._run_now(email) == 0
    assert notification_agent._run_now(email) == 0

    out = capsys.readouterr().out
    assert "New notifications: 1" in out and "already_sent" in out
    assert len(_notes(db, investor["user"])) == 1
    run = db.query(AgentRun).filter(AgentRun.trigger == "cli").first()
    assert run.scope_user_id == investor["user"].id
