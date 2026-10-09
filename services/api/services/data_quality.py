"""
Data-quality check of the served (split-adjusted) price series (Workflow.md Step 2.11).

Lists every one-day close-to-close move beyond MOVE_LIMIT and gives the reason the data can
show. Phase 3 leaves out of training any stock with an "unexplained" move until it has been
checked against PSX's own historical prices (Memory.md §4).

    python -m services.data_quality > ../../docs/data-quality/<date>.md
"""

import datetime
import sys
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from core.database import SessionLocal
from integrations.market_data import MarketDataClient, MarketDataUnavailable
from models.stock import PricePoint, Stock, StockSplit
from services.split_adjustment import AFTER_SPLIT_BARS, METHOD_VERSION

# Moves are compared after rounding to 0.1%: a close at exactly the +/-10% daily limit is
# a normal limit-up/limit-down day, not an outlier
MOVE_LIMIT = 10.0
PSX_TIMEZONE = ZoneInfo("Asia/Karachi")


@dataclass(frozen=True)
class Outlier:
    ticker: str
    day: datetime.date
    previous_day: datetime.date
    previous_close: float
    close: float
    move_pct: float
    reason: str


def _skipped_weekdays(previous_day: datetime.date, day: datetime.date) -> int:
    return sum(
        1
        for n in range(1, (day - previous_day).days)
        if (previous_day + datetime.timedelta(days=n)).weekday() < 5
    )


def _reason(
    day: datetime.date,
    previous_day: datetime.date,
    move_pct: float,
    dividend_dates: set[datetime.date],
    split_dates: list[datetime.date],
) -> str:
    if move_pct < 0 and day in dividend_dates:
        return "ex-dividend day (prices are not dividend-adjusted)"
    near = [d for d in split_dates if abs((day - d).days) <= AFTER_SPLIT_BARS * 2]
    if near:
        return f"near the {near[0]} split"
    skipped = _skipped_weekdays(previous_day, day)
    if skipped:
        # Each session moves at most MOVE_LIMIT, so k+1 sessions can compound beyond it
        sessions = skipped + 1
        up, down = (1 + MOVE_LIMIT / 100) ** sessions - 1, 1 - (1 - MOVE_LIMIT / 100) ** sessions
        if -down * 100 <= move_pct <= up * 100:
            return f"spans {sessions} sessions ({skipped} weekday(s) without a usable bar)"
    return "unexplained"


def find_outliers(db: Session, stock: Stock, dividend_dates: set[datetime.date]) -> list[Outlier]:
    points = (
        db.query(PricePoint)
        .filter(
            PricePoint.stock_id == stock.id,
            PricePoint.quality_flag.is_(None),
            # The provider fills PSX holidays with zero-volume bars repeating the last close
            PricePoint.volume > 0,
        )
        .order_by(PricePoint.timestamp)
        .all()
    )
    split_dates = [
        s.split_date for s in db.query(StockSplit).filter(StockSplit.stock_id == stock.id)
    ]
    outliers = []
    for previous, point in zip(points, points[1:], strict=False):
        prev_close = float(previous.close) / float(previous.split_factor)
        close = float(point.close) / float(point.split_factor)
        move_pct = round((close / prev_close - 1) * 100, 1)
        if abs(move_pct) <= MOVE_LIMIT:
            continue
        day = point.timestamp.astimezone(PSX_TIMEZONE).date()
        previous_day = previous.timestamp.astimezone(PSX_TIMEZONE).date()
        outliers.append(
            Outlier(
                stock.ticker,
                day,
                previous_day,
                round(prev_close, 2),
                round(close, 2),
                move_pct,
                _reason(day, previous_day, move_pct, dividend_dates, split_dates),
            )
        )
    return outliers


def report(db: Session) -> str:
    rows: list[Outlier] = []
    for stock in db.query(Stock).order_by(Stock.ticker):
        try:
            dividends = set(MarketDataClient.get_dividend_dates(stock.ticker))
        except MarketDataUnavailable:
            dividends = set()
        rows += find_outliers(db, stock, dividends)

    unexplained = sorted({r.ticker for r in rows if r.reason == "unexplained"})
    lines = [
        f"# Price data quality — {datetime.date.today()}",
        "",
        f"Served series: split-adjusted with method `{METHOD_VERSION}`, flagged bars excluded.",
        "Zero-volume bars are skipped: the provider fills PSX holidays with bars that repeat",
        "the last close, which would otherwise hide a gap and fold two sessions into one day.",
        f"One-day moves beyond ±{MOVE_LIMIT:g}% (rounded to 0.1%): **{len(rows)}** in "
        f"**{len({r.ticker for r in rows})}** stocks; **{len(unexplained)}** stocks have at "
        "least one unexplained move.",
        "",
        "Stocks with an unexplained move: " + (", ".join(unexplained) or "none"),
        "",
        "| Ticker | Date | Previous bar | Previous close | Close | Move | Reason |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    lines += [
        f"| {r.ticker} | {r.day} | {r.previous_day} | {r.previous_close:,.2f} | "
        f"{r.close:,.2f} | {r.move_pct:+.1f}% | {r.reason} |"
        for r in rows
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    session = SessionLocal()
    try:
        sys.stdout.write(report(session))
    finally:
        session.close()
