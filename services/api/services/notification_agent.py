"""
The monitoring agent (PRD.md FR33-FR36, Phase 7). After the evening forecasts it checks every
active portfolio whose owner switched a suggestion type on, with the Phase 5 roll check, the
latest Phase 3 forecasts and Phase 4 sentiment, and stores what the rules
(services/notification_rules.py) find. Advisory only: nothing is ever traded.

- Skipped, with the reason in agent_runs, when the forecasts are stale or another run holds the
  lock. Safe to run twice: each suggestion has a dedupe key, unique per user.
- Every figure comes from stored data through the existing engines (cost engine, roll check);
  the text comes from the app's fixed English and Urdu templates.

    python -m services.notification_agent run-now --user <email>

runs the same rules, caps and dedupe for one user, for a demo without waiting for the schedule.
"""

import argparse
import datetime
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from core.config import settings
from core.database import engine
from crud.user import get_user_by_email
from ml.inference import ModelNotFoundError, load_bundle
from models.notification import AgentRun, Notification, NotificationPreference
from models.portfolio import Portfolio, PortfolioHolding
from models.prediction import Prediction
from services import cost_engine, notification_rules, notification_templates
from services.cost_engine import FilerStatus
from services.notification_rules import (
    ANOTHER_RUN_IN_PROGRESS,
    NO_MODEL,
    PKT,
    Forecast,
    Preferences,
    Suggestion,
)
from services.portfolio_service import (
    PredictionsUnavailable,
    Universe,
    load_universe,
    roll_check,
)

logger = logging.getLogger(__name__)

# pg advisory lock key: one agent run at a time across workers and the run-now command
AGENT_LOCK_KEY = 7_000_001


@dataclass
class Clock:
    """
    Wall time for the run. `start` is the real time unless a test pins it; elapsed time is
    always measured, so the stored latencies are real either way.
    """

    start: datetime.datetime
    _perf: float = field(default_factory=time.perf_counter)

    def now(self) -> datetime.datetime:
        return self.start + datetime.timedelta(seconds=time.perf_counter() - self._perf)


def _str(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def preferences_of(row: NotificationPreference) -> Preferences:
    return Preferences(
        buy_enabled=row.buy_enabled,
        sell_enabled=row.sell_enabled,
        roll_enabled=row.roll_enabled,
        sensitivity=row.sensitivity,
        daily_cap=row.daily_cap,
        quiet_hours_enabled=row.quiet_hours_enabled,
        quiet_start=row.quiet_start,
        quiet_end=row.quiet_end,
    )


# Suggestions per portfolio -----------------------------------------------------------------


def _sell_suggestions(db: Session, portfolio: Portfolio, universe: Universe) -> list[Suggestion]:
    rates = cost_engine.load_rates()
    snapshot = {row["ticker"]: row for row in portfolio.input_snapshot["candidates"]}
    found = []
    for holding in portfolio.holdings:
        ticker = holding.stock.ticker
        ctx = universe.eligible.get(ticker)
        if ctx is None or ctx.prediction.signal != "SELL":
            continue
        used = db.get(Prediction, holding.prediction_id) if holding.prediction_id else None
        since = used.generated_at if used else portfolio.generated_at
        newer = [
            Forecast(str(p.id), p.signal, p.generated_at)
            for p in db.query(Prediction)
            .filter(
                Prediction.stock_id == holding.stock_id,
                Prediction.model_version == universe.model_version,
                Prediction.generated_at > since,
            )
            .order_by(Prediction.generated_at.desc())
            .all()
        ]
        baseline = snapshot[ticker]["signal"]
        start = notification_rules.sell_streak_start(newer, baseline)
        if start is None:
            continue
        position = next(i for i, f in enumerate(newer) if f.id == start.id)
        previous = newer[position + 1].signal if position + 1 < len(newer) else baseline

        sale = cost_engine.sell(
            holding.shares,
            ctx.candidate.price,
            Decimal(holding.total_cost),
            FilerStatus(portfolio.filer_status),
            rates,
            Decimal(portfolio.commission_rate),
        )
        prediction = ctx.prediction
        found.append(
            Suggestion(
                rule="sell_forecast",
                strength=notification_rules.sell_strength(
                    ctx.low_confidence_reasons, ctx.sentiment_label
                ),
                ticker=ticker,
                dedupe_key=f"sell:{portfolio.id}:{ticker}:{start.id}",
                link=f"/stocks/{ticker}",
                data_as_of=ctx.as_of,
                params={
                    "ticker": ticker,
                    "name": holding.stock.name,
                    "as_of": ctx.as_of.isoformat(),
                    "from_signal": previous,
                    "shares": holding.shares,
                    "price": _str(ctx.candidate.price),
                    "confidence_score": _str(prediction.confidence_score),
                    "low_confidence_threshold": settings.LOW_CONFIDENCE_THRESHOLD,
                    "low_confidence_reasons": ctx.low_confidence_reasons,
                    "signal_probability": _str(prediction.signal_probability),
                    "sentiment_label": ctx.sentiment_label,
                    "counted_headlines": ctx.counted_headlines,
                    "sale": {
                        "gross": _str(sale.gross),
                        "charges_total": _str(sale.charges.total),
                        "cgt": _str(sale.cgt),
                        "net_proceeds": _str(sale.net_proceeds),
                        "total_cost": _str(sale.total_cost),
                        "net_return": _str(sale.net_return),
                    },
                    "filer_status": portfolio.filer_status,
                },
            )
        )
    return found


def _roll_suggestions(db: Session, portfolio: Portfolio, universe: Universe) -> list[Suggestion]:
    check = roll_check(db, portfolio, universe)
    names = {h.stock.ticker: h.stock.name for h in portfolio.holdings}
    found = []
    for row in check["holdings"]:
        if row["status"] != "suggested":
            continue
        ticker, replacement = row["ticker"], row["replacement"]
        held = universe.eligible.get(ticker)
        other = universe.eligible.get(replacement["ticker"])
        found.append(
            Suggestion(
                rule="roll_suggested",
                strength=notification_rules.roll_strength(
                    held.low_confidence_reasons if held else None,
                    other.low_confidence_reasons if other else None,
                ),
                ticker=ticker,
                dedupe_key=f"roll:{portfolio.id}:{ticker}:{replacement['ticker']}",
                link="/portfolio",
                data_as_of=universe.prices_as_of,
                params={
                    "ticker": ticker,
                    "name": names[ticker],
                    "as_of": universe.prices_as_of.isoformat(),
                    "trading_days": row["trading_days"],
                    "holding_return_pct": row["holding_return_pct"],
                    "benchmark_return_pct": row["benchmark_return_pct"],
                    "relative_return_pct": row["relative_return_pct"],
                    "threshold_pct": row["threshold_pct"],
                    "replacement": {
                        **replacement,
                        "name": other.stock.name if other else None,
                    },
                    "sale": row["sale"],
                    "purchase": row["purchase"],
                    "switch_cost": row["switch_cost"],
                    "expected_benefit": row["expected_benefit"],
                    "low_confidence_reasons": held.low_confidence_reasons if held else None,
                    "replacement_low_confidence_reasons": (
                        other.low_confidence_reasons if other else None
                    ),
                },
            )
        )
    return found


def _idle_suggestion(portfolio: Portfolio) -> list[Suggestion]:
    idle = portfolio.input_snapshot["idle"]
    if not idle["flagged"]:
        return []
    return [
        Suggestion(
            rule="idle_cash",
            strength=None,
            ticker=None,
            dedupe_key=f"idle:{portfolio.id}",
            link="/portfolio",
            data_as_of=portfolio.prices_as_of,
            params={
                "amount": _str(portfolio.idle_cash),
                "blocked_by": idle["blocked_by"],
                "as_of": portfolio.prices_as_of.isoformat(),
            },
        )
    ]


def portfolio_suggestions(db: Session, portfolio: Portfolio) -> list[Suggestion]:
    universe = load_universe(db, portfolio.shariah_only, list(portfolio.excluded_tickers))
    return (
        _roll_suggestions(db, portfolio, universe)
        + _sell_suggestions(db, portfolio, universe)
        + _idle_suggestion(portfolio)
    )


# Storing -----------------------------------------------------------------------------------


def _stored_keys(db: Session, user_id) -> set[str]:
    rows = db.query(Notification.dedupe_key).filter(Notification.user_id == user_id).all()
    return {key for (key,) in rows}


def _stored_today(db: Session, user_id, now: datetime.datetime) -> int:
    local = now.astimezone(PKT)
    start = datetime.datetime.combine(local.date(), datetime.time(), PKT)
    return (
        db.query(func.count(Notification.id))
        .filter(
            Notification.user_id == user_id,
            Notification.sent_at >= start,
            Notification.sent_at < start + datetime.timedelta(days=1),
        )
        .scalar()
    )


def _store(
    db: Session,
    run: AgentRun,
    portfolio: Portfolio,
    prefs: NotificationPreference,
    suggestion: Suggestion,
    detected_at: datetime.datetime,
    detected_perf: float,
    clock: Clock,
    model_version: str,
) -> uuid.UUID | None:
    """Inserts one notification; None when an earlier (or parallel) run already stored it."""
    push_status, push_after = "off", None
    if prefs.push_enabled:
        rules_prefs = preferences_of(prefs)
        if notification_rules.in_quiet_hours(rules_prefs, clock.now()):
            push_status = "waiting_quiet_hours"
            push_after = notification_rules.quiet_hours_end(rules_prefs, clock.now())
        else:
            push_status = "pending"
    stmt = (
        insert(Notification)
        .values(
            id=uuid.uuid4(),
            user_id=portfolio.user_id,
            portfolio_id=portfolio.id,
            agent_run_id=run.id,
            type=suggestion.type,
            rule=suggestion.rule,
            strength=suggestion.strength,
            ticker=suggestion.ticker,
            reasoning=notification_templates.reasoning(suggestion.rule, suggestion.params),
            params=suggestion.params,
            link=suggestion.link,
            data_as_of=suggestion.data_as_of,
            model_version=model_version,
            dedupe_key=suggestion.dedupe_key,
            detected_at=detected_at,
            sent_at=clock.now(),
            read=False,
            push_status=push_status,
            push_after=push_after,
        )
        .on_conflict_do_nothing(constraint="uq_notifications_user_dedupe")
        .returning(Notification.id)
    )
    notification_id = db.execute(stmt).scalar()
    db.commit()
    if notification_id is None:
        return None
    # FR35: from the moment the rule fired to the moment the note is in the user's list
    latency = round((time.perf_counter() - detected_perf) * 1000)
    db.query(Notification).filter(Notification.id == notification_id).update(
        {"delivery_latency_ms": latency}
    )
    db.commit()
    return notification_id


# The run -----------------------------------------------------------------------------------


@dataclass
class RunResult:
    run_id: uuid.UUID
    status: str
    skip_reason: str | None
    created: list[uuid.UUID]
    suppressed: list[dict]


def _finish(db: Session, run: AgentRun, clock: Clock, status: str, reason: str | None = None):
    run.status = status
    run.skip_reason = reason
    run.finished_at = clock.now()
    db.commit()
    if reason:
        logger.warning("Agent run %s skipped: %s", run.id, reason)


def _monitored(db: Session, scope_user_id) -> list[tuple[Portfolio, NotificationPreference]]:
    query = (
        db.query(Portfolio, NotificationPreference)
        .join(NotificationPreference, NotificationPreference.user_id == Portfolio.user_id)
        .filter(Portfolio.status == "active")
        .filter(
            NotificationPreference.buy_enabled
            | NotificationPreference.sell_enabled
            | NotificationPreference.roll_enabled
        )
    )
    if scope_user_id is not None:
        query = query.filter(Portfolio.user_id == scope_user_id)
    return query.order_by(Portfolio.generated_at).all()


def run(
    db: Session,
    trigger: str,
    dispatch: Callable[[uuid.UUID], None],
    scope_user_id=None,
    now: datetime.datetime | None = None,
) -> RunResult:
    """
    One agent run. `dispatch` receives the id of every new notification whose push should go
    now (the worker queues `send_notification`; the run-now command sends inline). `now` is
    for tests only; the schedule and the command always use the real time.
    """
    clock = Clock(now or datetime.datetime.now(datetime.timezone.utc))
    agent_run = AgentRun(
        id=uuid.uuid4(), trigger=trigger, scope_user_id=scope_user_id, started_at=clock.now()
    )
    db.add(agent_run)
    db.commit()
    result = RunResult(agent_run.id, "running", None, [], [])

    lock = engine.connect()
    try:
        locked = lock.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": AGENT_LOCK_KEY})
        if not locked.scalar():
            _finish(db, agent_run, clock, "skipped", ANOTHER_RUN_IN_PROGRESS)
            result.status, result.skip_reason = "skipped", ANOTHER_RUN_IN_PROGRESS
            return result
        try:
            _checked_run(db, agent_run, clock, dispatch, scope_user_id, result)
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": AGENT_LOCK_KEY})
            lock.commit()
    except Exception:
        db.rollback()
        agent_run = db.get(AgentRun, result.run_id)
        _finish(db, agent_run, clock, "failed")
        result.status = "failed"
        raise
    finally:
        lock.close()
    return result


def _checked_run(
    db: Session,
    agent_run: AgentRun,
    clock: Clock,
    dispatch: Callable[[uuid.UUID], None],
    scope_user_id,
    result: RunResult,
) -> None:
    try:
        bundle = load_bundle(settings.MODEL_DIR)
    except ModelNotFoundError:
        _finish(db, agent_run, clock, "skipped", NO_MODEL)
        result.status, result.skip_reason = "skipped", NO_MODEL
        return
    newest_generated, newest_as_of = (
        db.query(func.max(Prediction.generated_at), func.max(Prediction.as_of_date))
        .filter(Prediction.model_version == bundle.version)
        .one()
    )
    agent_run.model_version = bundle.version
    agent_run.forecasts_generated_at = newest_generated
    agent_run.data_as_of = newest_as_of
    problem = notification_rules.freshness_problem(newest_generated, newest_as_of, clock.now())
    if problem:
        agent_run.detail = {
            "newest_forecast_at": newest_generated.isoformat() if newest_generated else None,
            "newest_price_date": newest_as_of.isoformat() if newest_as_of else None,
            "checked_at": clock.now().isoformat(),
        }
        _finish(db, agent_run, clock, "skipped", problem)
        result.status, result.skip_reason = "skipped", problem
        return

    errors = []
    for portfolio, prefs in _monitored(db, scope_user_id):
        agent_run.portfolios_checked += 1
        try:
            found = portfolio_suggestions(db, portfolio)
        except PredictionsUnavailable as exc:
            errors.append({"portfolio_id": str(portfolio.id), "error": str(exc)})
            continue
        detected_at, detected_perf = clock.now(), time.perf_counter()
        selection = notification_rules.select(
            found,
            preferences_of(prefs),
            _stored_keys(db, portfolio.user_id),
            _stored_today(db, portfolio.user_id, clock.now()),
        )
        for suggestion, reason in selection.suppressed:
            entry = {
                "user_id": str(portfolio.user_id),
                "rule": suggestion.rule,
                "ticker": suggestion.ticker,
                "reason": reason,
            }
            result.suppressed.append(entry)
            if reason == notification_rules.CAP_REACHED:
                logger.info(
                    "Notification not stored, cap reached: user %s, %s %s",
                    portfolio.user_id,
                    suggestion.rule,
                    suggestion.ticker or "",
                )
        for suggestion in selection.accepted:
            notification_id = _store(
                db,
                agent_run,
                portfolio,
                prefs,
                suggestion,
                detected_at,
                detected_perf,
                clock,
                bundle.version,
            )
            if notification_id is None:
                result.suppressed.append(
                    {
                        "user_id": str(portfolio.user_id),
                        "rule": suggestion.rule,
                        "ticker": suggestion.ticker,
                        "reason": notification_rules.ALREADY_SENT,
                    }
                )
                continue
            result.created.append(notification_id)
            if db.get(Notification, notification_id).push_status == "pending":
                dispatch(notification_id)

    agent_run.notifications_created = len(result.created)
    agent_run.suppressed = result.suppressed
    if errors:
        agent_run.detail = {"errors": errors}
    _finish(db, agent_run, clock, "completed")
    result.status = "completed"
    logger.info(
        "Agent run %s: %d portfolio(s), %d notification(s), %d not stored",
        agent_run.id,
        agent_run.portfolios_checked,
        len(result.created),
        len(result.suppressed),
    )


def _run_now(email: str) -> int:
    from core.database import SessionLocal
    from services.notification_dispatch import dispatch

    db = SessionLocal()
    try:
        user = get_user_by_email(db, email)
        if user is None:
            print("No account with that email.")
            return 1
        if (
            not db.query(PortfolioHolding)
            .join(Portfolio)
            .filter(Portfolio.user_id == user.id, Portfolio.status == "active")
            .first()
        ):
            print("That account has no active portfolio; generate one first.")
            return 1

        def send_now(notification_id: uuid.UUID) -> None:
            dispatch(db, notification_id)

        outcome = run(db, "cli", send_now, scope_user_id=user.id)
        print(f"Agent run {outcome.run_id}: {outcome.status}")
        if outcome.skip_reason:
            print(f"Skipped: {outcome.skip_reason} (details in agent_runs)")
        print(f"New notifications: {len(outcome.created)}")
        for entry in outcome.suppressed:
            print(f"Not stored: {entry['rule']} {entry['ticker'] or ''} ({entry['reason']})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Run the monitoring agent on demand.")
    sub = parser.add_subparsers(dest="command", required=True)
    now_parser = sub.add_parser("run-now", help="Run the agent for one user now")
    now_parser.add_argument("--user", required=True, help="the account's email")
    args = parser.parse_args()
    raise SystemExit(_run_now(args.user))
