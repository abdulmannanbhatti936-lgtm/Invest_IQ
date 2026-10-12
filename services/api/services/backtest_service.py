"""
Backtests against the database (PRD.md FR29-FR32): gathers price, dividend, risk-free and index
data, runs services/backtest.py, stores the result with every input and data version, and
shapes the API payload. No arithmetic on money happens here.
"""

import datetime
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.config import settings
from core.portfolio_rules import RISK_RULES, VOLATILITY_WINDOW
from models.backtest import BacktestResult
from models.portfolio import Portfolio
from models.stock import PricePoint, Stock, StockDividend
from models.user import User
from services import backtest, backtest_metrics, cost_engine, index_data, risk_free
from services.allocation import CapitalTooLow, TooFewEligibleStocks
from services.backtest import Bar, History, Period, Simulation
from services.cost_engine import FilerStatus, to_paisa
from services.portfolio_service import Close, is_shariah_compliant, volatility
from services.split_adjustment import METHOD_VERSION as SPLIT_METHOD
from services.stock_service import PSX_TRADING_DATE, SERVED

MIN_YEARS = 3  # PRD.md FR30
STAND_IN_KIND = "forecast_stocks_equal_weight"
KSE100 = "KSE100"
# Closes needed before the start date for the start-date rules' volatility, with room for
# holidays (250 trading days is about 13 months)
VOLATILITY_LOOKBACK = datetime.timedelta(days=550)
RATIO_PLACES = Decimal("0.000001")


class UnknownStocks(Exception):
    def __init__(self, tickers: list[str]):
        super().__init__(f"Unknown stocks: {tickers}")
        self.tickers = tickers


@dataclass(frozen=True)
class StockRange:
    ticker: str
    name: str
    sector: str
    first_date: datetime.date
    last_date: datetime.date
    whole_split_factors: bool

    def max_years(self, end: datetime.date) -> int:
        years = end.year - self.first_date.year
        if (end.month, end.day) < (self.first_date.month, self.first_date.day):
            years -= 1
        return years


def stock_ranges(db: Session, tickers: list[str] | None = None) -> dict[str, StockRange]:
    """Each stock's served history, and whether every split factor is a whole number."""
    whole = func.bool_and(PricePoint.split_factor == func.round(PricePoint.split_factor))
    query = (
        db.query(
            Stock.ticker,
            Stock.name,
            Stock.sector,
            func.min(PSX_TRADING_DATE),
            func.max(PSX_TRADING_DATE),
            whole,
        )
        .join(PricePoint, PricePoint.stock_id == Stock.id)
        .filter(SERVED)
        .group_by(Stock.id)
    )
    if tickers is not None:
        query = query.filter(Stock.ticker.in_(tickers))
    return {
        row[0]: StockRange(row[0], row[1], row[2] or "", row[3], row[4], bool(row[5]))
        for row in query
    }


def universe(db: Session) -> dict:
    """Stocks a custom mix may use: at least three years of served history, whole splits."""
    ranges = stock_ranges(db)
    latest = max(r.last_date for r in ranges.values())
    stocks, left_out = [], []
    for r in sorted(ranges.values(), key=lambda r: r.ticker):
        if not r.whole_split_factors:
            left_out.append({"ticker": r.ticker, "reason": "split_not_supported"})
        elif r.max_years(latest) >= MIN_YEARS:
            stocks.append(
                {
                    "ticker": r.ticker,
                    "name": r.name,
                    "sector": r.sector,
                    "first_date": r.first_date,
                    "max_years": r.max_years(latest),
                }
            )
    return {
        "latest_date": latest,
        "min_years": MIN_YEARS,
        "max_years": max(s["max_years"] for s in stocks),
        "stocks": stocks,
        "left_out": left_out,
    }


def _histories(db: Session, tickers: list[str], since: datetime.date) -> dict[str, History]:
    stocks = {s.id: s.ticker for s in db.query(Stock).filter(Stock.ticker.in_(tickers))}
    bars: dict[str, list[Bar]] = {t: [] for t in stocks.values()}
    rows = (
        db.query(PricePoint.stock_id, PSX_TRADING_DATE, PricePoint.close, PricePoint.split_factor)
        .filter(PricePoint.stock_id.in_(stocks), SERVED, PSX_TRADING_DATE >= since)
        .order_by(PricePoint.stock_id, PricePoint.timestamp)
    )
    for stock_id, day, close, factor in rows:
        bars[stocks[stock_id]].append(Bar(day, Decimal(close), Decimal(factor)))
    dividends: dict[str, list[tuple[datetime.date, Decimal]]] = {t: [] for t in stocks.values()}
    for stock_id, ex_date, amount in (
        db.query(StockDividend.stock_id, StockDividend.ex_date, StockDividend.amount)
        .filter(StockDividend.stock_id.in_(stocks), StockDividend.ex_date >= since)
        .order_by(StockDividend.ex_date)
    ):
        dividends[stocks[stock_id]].append((ex_date, Decimal(amount)))
    return {t: History(t, bars[t], dividends[t]) for t in stocks.values()}


def _ratio(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(RATIO_PLACES, rounding=ROUND_HALF_UP)


def _metrics(m: backtest_metrics.Metrics) -> dict:
    return {
        "total_return": str(_ratio(m.total_return)),
        "total_return_before_sale": str(_ratio(m.total_return_before_sale)),
        "annualised_return": str(_ratio(m.annualised_return)),
        "sharpe_ratio": None if m.sharpe_ratio is None else str(_ratio(m.sharpe_ratio)),
        "max_drawdown": str(_ratio(m.max_drawdown.depth)),
        "drawdown_peak_date": m.max_drawdown.peak_date,
        "drawdown_trough_date": m.max_drawdown.trough_date,
        "win_rate": None if m.win_rate is None else str(_ratio(m.win_rate)),
        "months_won": m.months_won,
        "months_total": m.months_total,
    }


def _costs(sim: Simulation) -> dict:
    return {
        "buy_charges": str(sim.buy_charges),
        "dividends_gross": str(sim.dividends_gross),
        "wht": str(sim.wht),
        "sell_charges": str(sim.sell_charges),
        "cgt": str(sim.cgt),
        "idle_cash": str(sim.idle_cash),
        "end_value_before_sale": str(sim.values[-1]),
        "end_value_net": str(sim.end_value_net),
    }


def _holdings(sim: Simulation, names: dict[str, str], weights: dict[str, Decimal] | None) -> list:
    return [
        {
            "ticker": h.ticker,
            "name": names.get(h.ticker, h.ticker),
            "weight_pct": None if weights is None else str(weights[h.ticker] * 100),
            "buy_date": h.start_day,
            "shares_bought": h.purchase.shares,
            "buy_price": str(h.purchase.price),
            "buy_cost": str(h.purchase.total_cost),
            "dividends_net": str(sum((d.net for _, d in h.dividends), Decimal(0))),
            "dividend_payments": len(h.dividends),
            "sell_date": h.end_day,
            "shares_sold": h.sale.shares,
            "sell_price": str(h.sale.price),
            "sell_charges": str(h.sale.charges.total),
            "cgt": str(h.sale.cgt),
            "sale_net": str(h.sale.net_proceeds),
            "carried_forward_days": h.carried_forward_days,
        }
        for h in sim.holdings
    ]


@dataclass(frozen=True)
class RunInputs:
    kind: str
    portfolio: Portfolio | None
    weights: dict[str, Decimal]  # fractions of capital, total 1
    capital: Decimal
    filer_status: FilerStatus
    commission_rate: Decimal
    years: int


def _start_date_rules(
    db: Session,
    inputs: RunInputs,
    histories: dict[str, History],
    period: Period,
    all_days: list[datetime.date],
    rates: cost_engine.Rates,
    rf: risk_free.RiskFreeSeries,
    names: dict[str, str],
) -> tuple[dict, Simulation | None]:
    portfolio = inputs.portfolio
    if portfolio is None:
        return {"status": "not_applicable"}, None
    pool = {
        t: h
        for t, h in histories.items()
        if t in settings.tracked_tickers
        and t not in (portfolio.excluded_tickers or [])
        and (not portfolio.shariah_only or is_shariah_compliant(t))
    }
    bars = {}
    for history in pool.values():
        try:
            bars.update(backtest.start_bars([history], period, all_days))
        except backtest.InsufficientHistory:
            continue
    pool = {t: h for t, h in pool.items() if t in bars}
    sectors = {s.ticker: s.sector or "" for s in db.query(Stock).filter(Stock.ticker.in_(pool))}
    try:
        purchases = backtest.purchases_from_rules(
            pool,
            sectors,
            inputs.capital,
            bars,
            RISK_RULES[portfolio.risk_category],
            rates,
            inputs.commission_rate,
            VOLATILITY_WINDOW,
            lambda newest_first: volatility([Close(b.day, b.served) for b in newest_first]),
        )
    except TooFewEligibleStocks:
        return {"status": "not_possible", "reason": "too_few_stocks_with_history"}, None
    except CapitalTooLow:
        return {"status": "not_possible", "reason": "capital_too_low"}, None
    sim = backtest.simulate(
        purchases, bars, pool, inputs.capital, period, inputs.filer_status, rates,
        inputs.commission_rate,
    )  # fmt: skip
    metrics = backtest_metrics.compute(sim.dates, sim.values, rf, sim.end_value_net)
    weights = {
        t: (p.total_cost / inputs.capital).quantize(Decimal("0.0001")) for t, p in purchases.items()
    }
    return {
        "status": "available",
        "risk_category": portfolio.risk_category,
        "metrics": _metrics(metrics),
        "costs": _costs(sim),
        "holdings": _holdings(sim, names, weights),
    }, sim


def run(db: Session, user: User, inputs: RunInputs) -> BacktestResult:
    rates = cost_engine.load_rates()
    rf = risk_free.load()
    tickers = sorted(inputs.weights)
    ranges = stock_ranges(db, tickers)
    unknown = sorted(set(tickers) - ranges.keys())
    if unknown:
        raise UnknownStocks(unknown)
    for r in ranges.values():
        if not r.whole_split_factors:
            raise backtest.UnsupportedSplit(r.ticker)

    end = min(r.last_date for r in ranges.values())
    since = end.replace(year=end.year - inputs.years, day=min(end.day, 28)) - VOLATILITY_LOOKBACK
    stand_in = list(settings.tracked_tickers)
    histories = _histories(db, sorted(set(tickers) | set(stand_in)), since)
    all_days = sorted({b.day for h in histories.values() for b in h.bars})
    period = backtest.period_for(inputs.years, end, all_days)
    names = {s.ticker: s.name for s in db.query(Stock).filter(Stock.ticker.in_(histories))}

    holding_histories = {t: histories[t] for t in tickers}
    bars = backtest.start_bars(list(holding_histories.values()), period, all_days)
    purchases = backtest.purchases_from_weights(
        inputs.weights, inputs.capital, bars, rates, inputs.commission_rate
    )
    sim = backtest.simulate(
        purchases, bars, holding_histories, inputs.capital, period, inputs.filer_status, rates,
        inputs.commission_rate,
    )  # fmt: skip
    metrics = backtest_metrics.compute(sim.dates, sim.values, rf, sim.end_value_net)

    rules_payload, rules_sim = _start_date_rules(
        db, inputs, histories, period, all_days, rates, rf, names
    )

    stand_in_bars, stand_in_histories = {}, []
    for ticker in stand_in:
        try:
            stand_in_bars.update(backtest.start_bars([histories[ticker]], period, all_days))
            stand_in_histories.append(histories[ticker])
        except (backtest.InsufficientHistory, KeyError):
            continue
    bench = backtest.equal_weight_benchmark(stand_in_histories, stand_in_bars, period)
    bench_metrics = backtest_metrics.compute(bench.dates, bench.values, rf)

    loaded = index_data.latest_series(db, KSE100)
    kse = backtest.index_benchmark(loaded[1], period) if loaded else None
    if kse is None:
        kse_payload = {
            "status": "not_covering_period" if loaded else "awaiting_permission",
            "dataset_version": loaded[0] if loaded else None,
        }
    else:
        kse_payload = {
            "status": "available",
            "dataset_version": loaded[0],
            "metrics": _metrics(backtest_metrics.compute(kse.dates, kse.values, rf)),
        }

    def rupees(run_values: list[Decimal], i: int) -> str:
        return str(to_paisa(run_values[i] * inputs.capital))

    series = [
        {
            "date": day.isoformat(),
            "portfolio": str(sim.values[i]),
            "start_date_rules": None if rules_sim is None else str(rules_sim.values[i]),
            "benchmark": rupees(bench.values, i),
            "kse100": None if kse is None else rupees(kse.values, i),
        }
        for i, day in enumerate(period.calendar)
    ]

    result = BacktestResult(
        user_id=user.id,
        portfolio_id=inputs.portfolio.id if inputs.portfolio else None,
        kind=inputs.kind,
        years=inputs.years,
        period_start=period.start,
        period_end=period.end,
        trading_days=len(period.calendar) - 1,
        carried_forward_days=sim.carried_forward_days,
        capital=inputs.capital,
        filer_status=inputs.filer_status.value,
        commission_rate=inputs.commission_rate,
        rates_version=rates.version,
        risk_free_version=rf.version,
        price_adjustment=SPLIT_METHOD,
        dividends_source="yahoo",
        prices_as_of=end,
        method_version=backtest.METHOD_VERSION,
        inputs={
            "holdings": [
                {"ticker": t, "name": names.get(t, t), "weight_pct": str(w * 100)}
                for t, w in sorted(inputs.weights.items())
            ]
        },
        buy_charges=sim.buy_charges,
        dividends_gross=sim.dividends_gross,
        wht=sim.wht,
        sell_charges=sim.sell_charges,
        cgt=sim.cgt,
        idle_cash=sim.idle_cash,
        end_value_before_sale=sim.values[-1],
        end_value_net=sim.end_value_net,
        total_return=_ratio(metrics.total_return),
        total_return_before_sale=_ratio(metrics.total_return_before_sale),
        annualised_return=_ratio(metrics.annualised_return),
        sharpe_ratio=_ratio(metrics.sharpe_ratio),
        max_drawdown=_ratio(metrics.max_drawdown.depth),
        drawdown_peak_date=metrics.max_drawdown.peak_date,
        drawdown_trough_date=metrics.max_drawdown.trough_date,
        win_rate=_ratio(metrics.win_rate),
        months_won=metrics.months_won,
        months_total=metrics.months_total,
        holdings=_json(_holdings(sim, names, inputs.weights)),
        start_date_rules=_json(rules_payload),
        benchmark=_json(
            {"kind": STAND_IN_KIND, "tickers": bench.tickers, "metrics": _metrics(bench_metrics)}
        ),
        kse100=_json(kse_payload),
        risk_free=_json(rf.summary(period.start, period.end)),
        series=series,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def _json(value):
    """Dates to ISO strings so the payload can be stored as JSONB."""
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json(v) for v in value]
    if isinstance(value, datetime.date):
        return value.isoformat()
    return value


def portfolio_inputs(portfolio: Portfolio, years: int) -> RunInputs:
    # Stored target weights are percent with 4 decimals and total 100
    weights = {h.stock.ticker: Decimal(h.target_weight) / 100 for h in portfolio.holdings}
    return RunInputs(
        kind="portfolio",
        portfolio=portfolio,
        weights=weights,
        capital=Decimal(portfolio.capital),
        filer_status=FilerStatus(portfolio.filer_status),
        commission_rate=Decimal(portfolio.commission_rate),
        years=years,
    )


def owned_result(db: Session, user: User, result_id: uuid.UUID) -> BacktestResult | None:
    return (
        db.query(BacktestResult)
        .filter(BacktestResult.id == result_id, BacktestResult.user_id == user.id)
        .first()
    )


def result_payload(result: BacktestResult) -> dict:
    return {
        "id": result.id,
        "kind": result.kind,
        "portfolio_id": result.portfolio_id,
        "created_at": result.created_at,
        "period": {
            "years": result.years,
            "start": result.period_start,
            "end": result.period_end,
            "trading_days": result.trading_days,
        },
        "inputs": {
            "capital": str(result.capital),
            "filer_status": result.filer_status,
            "commission_pct": str(
                (Decimal(result.commission_rate) * 100).quantize(Decimal("0.001"))
            ),
            "holdings": result.inputs["holdings"],
        },
        "portfolio": {
            "metrics": {
                "total_return": str(result.total_return),
                "total_return_before_sale": str(result.total_return_before_sale),
                "annualised_return": str(result.annualised_return),
                "sharpe_ratio": _str(result.sharpe_ratio),
                "max_drawdown": str(result.max_drawdown),
                "drawdown_peak_date": result.drawdown_peak_date,
                "drawdown_trough_date": result.drawdown_trough_date,
                "win_rate": _str(result.win_rate),
                "months_won": result.months_won,
                "months_total": result.months_total,
            },
            "costs": {
                "buy_charges": str(result.buy_charges),
                "dividends_gross": str(result.dividends_gross),
                "wht": str(result.wht),
                "sell_charges": str(result.sell_charges),
                "cgt": str(result.cgt),
                "idle_cash": str(result.idle_cash),
                "end_value_before_sale": str(result.end_value_before_sale),
                "end_value_net": str(result.end_value_net),
            },
            "holdings": result.holdings,
        },
        "start_date_rules": result.start_date_rules,
        "benchmark": result.benchmark,
        "kse100": result.kse100,
        "risk_free": result.risk_free,
        "assumptions": {
            "rates_version": result.rates_version,
            "price_adjustment": result.price_adjustment,
            "dividends_source": result.dividends_source,
            "dividends_checked": False,
            "prices_as_of": result.prices_as_of,
            "method_version": result.method_version,
            "carried_forward_days": result.carried_forward_days,
        },
        "series": result.series,
    }


def _str(value) -> str | None:
    return None if value is None else str(value)
