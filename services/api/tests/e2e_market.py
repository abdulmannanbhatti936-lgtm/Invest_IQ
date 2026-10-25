"""
MOCK market for the Playwright run (apps/web/e2e): six invented stocks with synthetic daily
closes, a few invented dividends and invented forecasts from the MOCK model in
tests/fixtures/model_e2e. Only ever written to the *_test database (tests/testdb.py), and
removed again by the E2E teardown and at the start of every pytest session. None of these
tickers or prices is PSX data (CLAUDE.md: mock data is labelled and never reaches a demo).
"""

import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy.orm import Session

from models.prediction import Prediction
from models.stock import PricePoint, Stock, StockDividend
from tests.synthetic import make_ohlcv

E2E_TICKERS = ["MOCKE2EA", "MOCKE2EB", "MOCKE2EC", "MOCKE2ED", "MOCKE2EE", "MOCKE2EF"]
E2E_MODEL_DIR = Path(__file__).resolve().parent / "fixtures" / "model_e2e"
E2E_MODEL_VERSION = "MOCK-e2e-v1"
# Four and a half years of business days, so a 3-year backtest has a year of closes before it
TRADING_DAYS = 1150
LAST_DAY = datetime.date(2026, 10, 9)
PKT = ZoneInfo("Asia/Karachi")
# The MOCK forecasts are dated like the evening job's (Architecture.md §9: 18:30 PKT) on the last
# MOCK day, so the monitoring agent's "forecasts made today" check can run against this market
FORECAST_TIME = datetime.datetime.combine(LAST_DAY, datetime.time(18, 30), PKT)


def clear_market(db: Session) -> int:
    """Removes the MOCK stocks; their bars, dividends and forecasts go with them (CASCADE)."""
    deleted = (
        db.query(Stock).filter(Stock.ticker.in_(E2E_TICKERS)).delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def seed_market(db: Session) -> None:
    clear_market(db)
    days = pd.bdate_range(end=LAST_DAY, periods=TRADING_DAYS)
    for i, ticker in enumerate(E2E_TICKERS):
        stock = Stock(
            ticker=ticker, name=f"MOCK E2E company {ticker[-1]}", sector=f"MOCK sector {i % 3}"
        )
        db.add(stock)
        db.flush()
        closes = [
            Decimal(str(round(c, 2)))
            for c in make_ohlcv(TRADING_DAYS, seed=51 + i, start_price=40.0 + 15 * i)["close"]
        ]
        db.add_all(
            PricePoint(
                stock_id=stock.id,
                timestamp=datetime.datetime.combine(day.date(), datetime.time(), PKT),
                close=close,
                volume=100_000,
            )
            for day, close in zip(days, closes, strict=True)
        )
        if i % 2 == 0:
            db.add(
                StockDividend(
                    stock_id=stock.id,
                    ex_date=days[-300].date(),
                    amount=Decimal("2"),
                    source="MOCK",
                )
            )
        db.add(
            Prediction(
                stock_id=stock.id,
                model_version=E2E_MODEL_VERSION,
                forecast_price=closes[-1] * Decimal("1.002"),
                last_close=closes[-1],
                confidence_score=Decimal("0.5"),
                signal="HOLD",
                signal_probability=Decimal("0.4"),
                as_of_date=days[-1].date(),
                generated_at=FORECAST_TIME,
            )
        )
    db.commit()
