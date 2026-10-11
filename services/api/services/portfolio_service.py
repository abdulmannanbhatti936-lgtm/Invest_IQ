"""
Portfolio generation, exclusion and the roll check against the database (PRD.md FR23-FR28).
The allocation (services/allocation.py), rolling (services/rolling.py) and all rupee
figures (services/cost_engine.py) are pure; this module only gathers their inputs, stores
the result with everything needed to explain it later, and shapes the API payloads.
"""

import csv
import datetime
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from core.config import settings
from core.portfolio_rules import (
    RISK_RULES,
    ROLL_WINDOW_TRADING_DAYS,
    SHARIAH_FILE,
    SHARIAH_LIST_VERSION,
    VOLATILITY_WINDOW,
)
from ml.inference import ModelNotFoundError, load_bundle
from models.portfolio import Portfolio, PortfolioHolding
from models.prediction import Prediction
from models.risk_profile import RiskProfile
from models.stock import PricePoint, Stock, StockDividend
from models.user import User
from services import cost_engine
from services.allocation import (
    Allocation,
    Candidate,
    CapitalTooLow,
    allocate,
    minimum_capital,
)
from services.cost_engine import DATA_DIR, FilerStatus, Rates, to_paisa
from services.prediction_service import latest_prediction, low_confidence_reasons
from services.rolling import HeldStock, Replacement, RollCheck, check_holding
from services.sentiment_service import stock_sentiment
from services.stock_service import SERVED

PKT = ZoneInfo("Asia/Karachi")
DIVIDEND_WINDOW = datetime.timedelta(days=365)
BENCHMARK_LABEL = "equal_weight_forecast_stocks"


class PredictionsUnavailable(Exception):
    """No current model or no current forecasts to build a portfolio from."""


class TickerNotInPortfolio(Exception):
    pass


class PortfolioArchived(Exception):
    pass


def _str(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _pct(value: Decimal, places: str = "0.01") -> Decimal:
    """A fraction as a percentage for display, e.g. 0.123456 -> 12.35."""
    return (value * 100).quantize(Decimal(places), rounding=ROUND_HALF_UP)


@lru_cache
def shariah_statuses() -> dict[str, str]:
    """PSX's Shariah review (the full compliance pool, not only KMI-30 members)."""
    with open(DATA_DIR / SHARIAH_FILE, encoding="utf-8") as f:
        return {row["ticker"]: row["final_status"] for row in csv.DictReader(f)}


def is_shariah_compliant(ticker: str) -> bool:
    return shariah_statuses().get(ticker) == "Compliant"


@dataclass(frozen=True)
class Close:
    date: datetime.date
    close: Decimal


def _close(point: PricePoint) -> Close:
    return Close(
        point.timestamp.astimezone(PKT).date(),
        Decimal(point.close) / Decimal(point.split_factor),
    )


def recent_closes(db: Session, stock: Stock, limit: int) -> list[Close]:
    """Served (split-adjusted) closes, newest first."""
    points = (
        db.query(PricePoint)
        .filter(PricePoint.stock_id == stock.id, SERVED)
        .order_by(PricePoint.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [_close(p) for p in points]


def close_on_or_before(db: Session, stock: Stock, day: datetime.date) -> Close | None:
    end = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time(), PKT)
    point = (
        db.query(PricePoint)
        .filter(PricePoint.stock_id == stock.id, SERVED, PricePoint.timestamp < end)
        .order_by(PricePoint.timestamp.desc())
        .first()
    )
    return _close(point) if point else None


def trading_days_after(db: Session, stock: Stock, day: datetime.date) -> int:
    start = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time(), PKT)
    return (
        db.query(PricePoint)
        .filter(PricePoint.stock_id == stock.id, SERVED, PricePoint.timestamp >= start)
        .count()
    )


def volatility(closes: list[Close]) -> Decimal:
    """Sample standard deviation of daily log returns, rounded to 6 decimals and stored."""
    returns = [
        (newer.close / older.close).ln() for newer, older in zip(closes, closes[1:], strict=False)
    ]
    mean = sum(returns, Decimal(0)) / len(returns)
    variance = sum(((r - mean) ** 2 for r in returns), Decimal(0)) / (len(returns) - 1)
    return variance.sqrt().quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class StockContext:
    stock: Stock
    prediction: Prediction
    candidate: Candidate
    as_of: datetime.date
    low_confidence_reasons: list[str]
    sentiment_label: str | None
    counted_headlines: int


@dataclass(frozen=True)
class Universe:
    model_version: str
    eligible: dict[str, StockContext]
    skipped: dict[str, str]  # ticker -> why it was left out

    @property
    def prices_as_of(self) -> datetime.date:
        return max(ctx.as_of for ctx in self.eligible.values())


def load_universe(db: Session, shariah_only: bool, excluded: list[str]) -> Universe:
    """
    The stocks a portfolio may hold: forecast by the current model, with a forecast made from
    the stock's latest served close, a full volatility window, and not filtered out.
    """
    try:
        bundle = load_bundle(settings.MODEL_DIR)
    except ModelNotFoundError as exc:
        raise PredictionsUnavailable("No current model") from exc

    eligible, skipped = {}, {}
    for ticker in sorted(bundle.metadata["tickers"]):
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()
        prediction = latest_prediction(db, stock, bundle.version) if stock else None
        if prediction is None:
            skipped[ticker] = "no_forecast"
            continue
        closes = recent_closes(db, stock, VOLATILITY_WINDOW + 1)
        if not closes or prediction.as_of_date != closes[0].date:
            skipped[ticker] = "forecast_not_current"
            continue
        if len(closes) < VOLATILITY_WINDOW + 1:
            skipped[ticker] = "short_history"
            continue
        if ticker in excluded:
            skipped[ticker] = "excluded"
            continue
        if shariah_only and not is_shariah_compliant(ticker):
            skipped[ticker] = "not_shariah_compliant"
            continue

        sentiment = stock_sentiment(db, stock)
        counted = sentiment["counted_headlines"]
        score = sentiment["score"]
        eligible[ticker] = StockContext(
            stock=stock,
            prediction=prediction,
            candidate=Candidate(
                ticker=ticker,
                sector=stock.sector or "",
                price=to_paisa(Decimal(prediction.last_close)),
                volatility=volatility(closes),
                expected_return=Decimal(prediction.forecast_price) / Decimal(prediction.last_close)
                - 1,
                signal=prediction.signal,
                signal_probability=(
                    None
                    if prediction.signal_probability is None
                    else Decimal(prediction.signal_probability)
                ),
                # The decayed mean is a float; 4 decimals, like the stored headline scores
                sentiment_score=(
                    Decimal(str(round(score, 4))) if counted and score is not None else None
                ),
            ),
            as_of=closes[0].date,
            low_confidence_reasons=low_confidence_reasons(prediction, bundle, ticker),
            sentiment_label=sentiment["label"],
            counted_headlines=counted,
        )
    if not eligible and not any(
        r in ("excluded", "not_shariah_compliant") for r in skipped.values()
    ):
        raise PredictionsUnavailable("No current forecasts")
    return Universe(bundle.version, eligible, skipped)


def _dividends(db: Session, stock: Stock, as_of: datetime.date) -> list[StockDividend]:
    return (
        db.query(StockDividend)
        .filter(
            StockDividend.stock_id == stock.id,
            StockDividend.ex_date > as_of - DIVIDEND_WINDOW,
            StockDividend.ex_date <= as_of,
        )
        .order_by(StockDividend.ex_date)
        .all()
    )


def _charges_payload(charges: cost_engine.Charges) -> dict:
    return {
        "commission": _str(charges.commission),
        "sales_tax": _str(charges.sales_tax),
        **{key: _str(amount) for key, amount in charges.fees},
        "total": _str(charges.total),
    }


def _projection(
    db: Session,
    ctx: StockContext,
    purchase: cost_engine.Purchase,
    filer_status: FilerStatus,
    rates: Rates,
    commission_rate: Decimal,
) -> dict:
    """Break-even, the one-day forecast exit and last year's dividends; all estimates."""
    shares, price, cost = purchase.shares, purchase.price, purchase.total_cost
    break_even = cost_engine.break_even_price(shares, cost, rates, commission_rate)
    exit_price = to_paisa(Decimal(ctx.prediction.forecast_price))
    sale = cost_engine.sell(shares, exit_price, cost, filer_status, rates, commission_rate)

    payments = _dividends(db, ctx.stock, ctx.as_of)
    per_share = sum((Decimal(d.amount) for d in payments), Decimal(0))
    dividends = None
    if per_share > 0:
        income = cost_engine.dividend_income(shares, per_share, filer_status, rates)
        dividends = {
            "per_share": _str(to_paisa(per_share)),
            "payments": [
                {"ex_date": d.ex_date.isoformat(), "amount": str(d.amount)} for d in payments
            ],
            "period_start": (ctx.as_of - DIVIDEND_WINDOW).isoformat(),
            "period_end": ctx.as_of.isoformat(),
            "gross": _str(income.gross),
            "wht_rate_pct": _str(_pct(rates.wht_rate(filer_status), "1")),
            "wht": _str(income.wht),
            "net": _str(income.net),
            "source": "yahoo",
        }
    return {
        "break_even_price": _str(break_even),
        "break_even_change_pct": _str(_pct(break_even / price - 1)),
        "round_trip_pct": _str(
            _pct(cost_engine.round_trip_rate(shares, price, rates, commission_rate))
        ),
        "forecast_exit": {
            "price": _str(exit_price),
            "gross": _str(sale.gross),
            "charges": _charges_payload(sale.charges),
            "proceeds": _str(sale.proceeds),
            "gain": _str(sale.gain),
            "cgt": _str(sale.cgt),
            "net_proceeds": _str(sale.net_proceeds),
            "net_return": _str(sale.net_return),
            "net_return_pct": _str(_pct(sale.net_return / cost)),
        },
        "dividends": dividends,
    }


def _snapshot(universe: Universe, allocation: Allocation, rules_name: str) -> dict:
    selected = {h.scored.ticker: h for h in allocation.holdings}
    rows = []
    for rank, s in enumerate(allocation.ranked, start=1):
        c = s.candidate
        ctx = universe.eligible[c.ticker]
        holding = selected.get(c.ticker)
        rows.append(
            {
                "ticker": c.ticker,
                "rank": rank,
                "selected": holding is not None,
                "unaffordable": c.ticker in allocation.unaffordable,
                "sector": c.sector,
                "price": _str(c.price),
                "volatility": _str(c.volatility),
                "forecast_price": _str(Decimal(ctx.prediction.forecast_price)),
                "last_close": _str(Decimal(ctx.prediction.last_close)),
                "expected_return": _str(c.expected_return),
                "signal": c.signal,
                "signal_probability": _str(c.signal_probability),
                "confidence_score": _str(Decimal(ctx.prediction.confidence_score)),
                "low_confidence_reasons": ctx.low_confidence_reasons,
                "sentiment_score": _str(c.sentiment_score),
                "sentiment_label": ctx.sentiment_label,
                "counted_headlines": ctx.counted_headlines,
                "forecast_component": _str(s.forecast_component),
                "signal_component": _str(s.signal_component),
                "sentiment_component": _str(s.sentiment_component),
                "tilt": _str(s.tilt),
                "risk_weight": _str(s.risk_weight),
                "raw_weight": _str(s.raw_weight),
                "untilted_weight": _str(holding.untilted_weight) if holding else None,
                "tilt_effect_pp": _str(holding.tilt_effect_pp) if holding else None,
            }
        )
    return {
        "risk_rules": rules_name,
        "candidates": rows,
        "skipped": universe.skipped,
        "idle": {
            "flagged": allocation.idle.flagged,
            "blocked_by": allocation.idle.blocked_by,
        },
    }


@dataclass(frozen=True)
class PortfolioInputs:
    capital: Decimal
    filer_status: FilerStatus
    shariah_only: bool
    excluded_tickers: list[str]
    commission_rate: Decimal | None


class CapitalBelowMinimum(Exception):
    def __init__(self, capital: Decimal, minimum: Decimal | None, category: str, as_of):
        super().__init__(f"Rs {capital} is below the minimum for {category}")
        self.capital = capital
        self.minimum = minimum
        self.category = category
        self.prices_as_of = as_of


def generate_portfolio(
    db: Session, user: User, profile: RiskProfile, inputs: PortfolioInputs
) -> Portfolio:
    category = profile.category.value
    rules = RISK_RULES[category]
    rates = cost_engine.load_rates()
    commission_rate = cost_engine.check_commission_rate(
        inputs.commission_rate or rates.commission_rate, rates
    )
    universe = load_universe(db, inputs.shariah_only, inputs.excluded_tickers)
    candidates = [ctx.candidate for ctx in universe.eligible.values()]
    try:
        allocation = allocate(candidates, inputs.capital, rules, rates, commission_rate)
    except CapitalTooLow as exc:
        minimum = minimum_capital(candidates, inputs.capital, rules, rates, commission_rate)
        raise CapitalBelowMinimum(inputs.capital, minimum, category, universe.prices_as_of) from exc

    for old in db.query(Portfolio).filter(
        Portfolio.user_id == user.id, Portfolio.status == "active"
    ):
        old.status = "archived"
    db.flush()

    portfolio = Portfolio(
        user_id=user.id,
        status="active",
        risk_category=category,
        capital=inputs.capital,
        filer_status=inputs.filer_status.value,
        shariah_only=inputs.shariah_only,
        excluded_tickers=sorted(inputs.excluded_tickers),
        commission_rate=commission_rate,
        rates_version=rates.version,
        model_version=universe.model_version,
        prices_as_of=universe.prices_as_of,
        shariah_list_version=SHARIAH_LIST_VERSION if inputs.shariah_only else None,
        input_snapshot=_snapshot(universe, allocation, category),
        gross_total=allocation.gross_total,
        charges_total=allocation.charges_total,
        cost_total=allocation.cost_total,
        idle_cash=allocation.idle.amount,
    )
    for position, planned in enumerate(allocation.holdings):
        ctx = universe.eligible[planned.scored.ticker]
        purchase = planned.purchase
        portfolio.holdings.append(
            PortfolioHolding(
                stock_id=ctx.stock.id,
                prediction_id=ctx.prediction.id,
                position=position,
                shares=purchase.shares,
                reference_price=purchase.price,
                target_weight=_pct(planned.target_weight, "0.0001"),
                allocation_pct=_pct(purchase.total_cost / inputs.capital, "0.0001"),
                gross_value=purchase.gross,
                commission=purchase.charges.commission,
                sales_tax=purchase.charges.sales_tax,
                buy_charges=purchase.charges.total,
                total_cost=purchase.total_cost,
                projection=_projection(
                    db, ctx, purchase, inputs.filer_status, rates, commission_rate
                ),
                # The rates file's fee keys are the column names
                **dict(purchase.charges.fees),
            )
        )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


def active_portfolio(db: Session, user: User) -> Portfolio | None:
    return (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user.id, Portfolio.status == "active")
        .first()
    )


def owned_portfolio(db: Session, user: User, portfolio_id) -> Portfolio | None:
    return (
        db.query(Portfolio)
        .filter(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
        .first()
    )


def exclusion_inputs(portfolio: Portfolio, ticker: str) -> PortfolioInputs:
    """FR27: the same inputs with one more stock excluded, for a new portfolio."""
    if portfolio.status != "active":
        raise PortfolioArchived(str(portfolio.id))
    if ticker not in {h.stock.ticker for h in portfolio.holdings}:
        raise TickerNotInPortfolio(ticker)
    return PortfolioInputs(
        capital=Decimal(portfolio.capital),
        filer_status=FilerStatus(portfolio.filer_status),
        shariah_only=portfolio.shariah_only,
        excluded_tickers=sorted({*portfolio.excluded_tickers, ticker}),
        commission_rate=Decimal(portfolio.commission_rate),
    )


def benchmark_return(db: Session, since: datetime.date) -> tuple[Decimal | None, int]:
    """
    Equal-weight average return of the forecast stocks since `since`. Used because Yahoo has
    no KSE-100 index series (checked 2026-10-11: ^KSE, ^KSE100 and KSE100.KA return no data).
    """
    returns = []
    for ticker in settings.tracked_tickers:
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()
        start = close_on_or_before(db, stock, since) if stock else None
        latest = recent_closes(db, stock, 1) if stock else []
        if start and latest:
            returns.append(latest[0].close / start.close - 1)
    if not returns:
        return None, 0
    return sum(returns, Decimal(0)) / len(returns), len(returns)


def roll_check(db: Session, portfolio: Portfolio) -> dict:
    if portfolio.status != "active":
        raise PortfolioArchived(str(portfolio.id))
    rates = cost_engine.load_rates()
    benchmark, benchmark_stocks = benchmark_return(db, portfolio.prices_as_of)
    universe = load_universe(db, portfolio.shariah_only, list(portfolio.excluded_tickers))
    snapshot = {row["ticker"]: row for row in portfolio.input_snapshot["candidates"]}
    held_tickers = {h.stock.ticker for h in portfolio.holdings}
    replacements = [
        Replacement(t, ctx.candidate.price, ctx.candidate.expected_return)
        for t, ctx in universe.eligible.items()
        if t not in held_tickers
    ]
    filer = FilerStatus(portfolio.filer_status)
    commission_rate = Decimal(portfolio.commission_rate)

    checks = []
    for holding in portfolio.holdings:
        ticker = holding.stock.ticker
        latest = recent_closes(db, holding.stock, 1)
        ctx = universe.eligible.get(ticker)
        saved = snapshot[ticker]
        held = HeldStock(
            ticker=ticker,
            shares=holding.shares,
            total_cost=Decimal(holding.total_cost),
            entry_price=Decimal(holding.reference_price),
            current_price=(
                to_paisa(latest[0].close) if latest else Decimal(holding.reference_price)
            ),
            volatility=Decimal(saved["volatility"]),
            expected_return=(
                ctx.candidate.expected_return if ctx else Decimal(saved["expected_return"])
            ),
            signal=ctx.candidate.signal if ctx else saved["signal"],
        )
        checks.append(
            check_holding(
                held,
                benchmark or Decimal(0),
                trading_days_after(db, holding.stock, portfolio.prices_as_of),
                replacements,
                filer,
                rates,
                commission_rate,
            )
        )
    return {
        "portfolio_id": portfolio.id,
        "checked_at": datetime.datetime.now(datetime.timezone.utc),
        "required_trading_days": ROLL_WINDOW_TRADING_DAYS,
        "benchmark": {
            "kind": BENCHMARK_LABEL,
            "stock_count": benchmark_stocks,
            "since": portfolio.prices_as_of,
            "return_pct": _str(_pct(benchmark)) if benchmark is not None else None,
        },
        "holdings": [_roll_payload(c) for c in checks],
    }


def _roll_payload(check: RollCheck) -> dict:
    payload = {
        "ticker": check.ticker,
        "status": check.status.value,
        "trading_days": check.trading_days,
        "holding_return_pct": _str(_pct(check.holding_return)),
        "benchmark_return_pct": _str(_pct(check.benchmark_return)),
        "relative_return_pct": _str(_pct(check.relative_return)),
        "threshold_pct": _str(_pct(check.threshold)),
        "weak_forecast": check.weak_forecast,
        "replacement": None,
        "sale": None,
        "purchase": None,
        "switch_cost": _str(check.switch_cost),
        "expected_benefit": _str(check.expected_benefit),
    }
    if check.replacement:
        payload["replacement"] = {
            "ticker": check.replacement.ticker,
            "price": _str(check.replacement.price),
            "expected_change_pct": _str(_pct(check.replacement.expected_return, "0.001")),
        }
    if check.sale:
        payload["sale"] = {
            "gross": _str(check.sale.gross),
            "charges_total": _str(check.sale.charges.total),
            "cgt": _str(check.sale.cgt),
            "net_proceeds": _str(check.sale.net_proceeds),
        }
    if check.purchase:
        payload["purchase"] = {
            "shares": check.purchase.shares,
            "gross": _str(check.purchase.gross),
            "charges_total": _str(check.purchase.charges.total),
        }
    return payload


def rates_payload(rates: Rates) -> dict:
    return {
        "version": rates.version,
        "checked_on": rates.checked_on,
        "unverified": [f.key for f in rates.fees if f.status != "verified"]
        + (["cgt"] if rates.cgt_status != "verified" else []),
        "not_modelled": list(rates.not_modelled),
        "cgt_non_filer_label": rates.cgt_non_filer_label,
        "commission_floor_pct": _str(_pct(rates.commission_rate, "0.001")),
        "commission_max_pct": _str(_pct(rates.commission_max_rate, "0.001")),
    }


def portfolio_payload(portfolio: Portfolio) -> dict:
    rates = cost_engine.load_rates()
    snapshot = {row["ticker"]: row for row in portfolio.input_snapshot["candidates"]}
    holdings = []
    for h in portfolio.holdings:
        why = snapshot[h.stock.ticker]
        holdings.append(
            {
                "ticker": h.stock.ticker,
                "name": h.stock.name,
                "sector": h.stock.sector,
                "shares": h.shares,
                "price": _str(h.reference_price),
                "target_weight_pct": _str(h.target_weight),
                "allocation_pct": _str(h.allocation_pct),
                "gross": _str(h.gross_value),
                "charges": {
                    "commission": _str(h.commission),
                    "sales_tax": _str(h.sales_tax),
                    "cdc_fee": _str(h.cdc_fee),
                    "psx_trading_fee": _str(h.psx_trading_fee),
                    "psx_regulatory_fee": _str(h.psx_regulatory_fee),
                    "secp_levy": _str(h.secp_levy),
                    "nccpl_trade_fee": _str(h.nccpl_trade_fee),
                    "nccpl_secp_fee": _str(h.nccpl_secp_fee),
                    "total": _str(h.buy_charges),
                },
                "total_cost": _str(h.total_cost),
                **h.projection,
                "why": {
                    "rank": why["rank"],
                    "volatility_pct": _str(_pct(Decimal(why["volatility"]), "0.001")),
                    "forecast_price": why["forecast_price"],
                    "last_close": why["last_close"],
                    "expected_change_pct": _str(_pct(Decimal(why["expected_return"]), "0.001")),
                    "confidence_score": why["confidence_score"],
                    "low_confidence_reasons": why["low_confidence_reasons"],
                    "low_confidence_threshold": settings.LOW_CONFIDENCE_THRESHOLD,
                    "signal": why["signal"],
                    "signal_probability": why["signal_probability"],
                    "sentiment_label": why["sentiment_label"],
                    "sentiment_score": why["sentiment_score"],
                    "counted_headlines": why["counted_headlines"],
                    "tilt_effect_pp": _str(
                        Decimal(why["tilt_effect_pp"]).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        )
                    ),
                },
            }
        )
    idle = portfolio.input_snapshot["idle"]
    return {
        "id": portfolio.id,
        "status": portfolio.status,
        "generated_at": portfolio.generated_at,
        "risk_category": portfolio.risk_category,
        "capital": _str(portfolio.capital),
        "filer_status": portfolio.filer_status,
        "shariah_only": portfolio.shariah_only,
        "shariah_list_version": portfolio.shariah_list_version,
        "excluded_tickers": portfolio.excluded_tickers,
        "commission_pct": _str(_pct(Decimal(portfolio.commission_rate), "0.001")),
        "model_version": portfolio.model_version,
        "prices_as_of": portfolio.prices_as_of,
        "rates": {**rates_payload(rates), "version": portfolio.rates_version},
        "totals": {
            "gross": _str(portfolio.gross_total),
            "charges": _str(portfolio.charges_total),
            "cost": _str(portfolio.cost_total),
            "idle_cash": _str(portfolio.idle_cash),
        },
        "idle": {
            "amount": _str(portfolio.idle_cash),
            "flagged": idle["flagged"],
            "blocked_by": idle["blocked_by"],
        },
        "holdings": holdings,
    }
