import datetime

from models.stock import PricePoint, Stock, StockSplit
from services.data_quality import _reason, _skipped_weekdays, find_outliers

PKT = datetime.timezone(datetime.timedelta(hours=5))
D = datetime.date


def test_skipped_weekdays_ignores_weekends():
    assert _skipped_weekdays(D(2023, 7, 28), D(2023, 7, 31)) == 0  # Fri -> Mon
    assert _skipped_weekdays(D(2023, 7, 26), D(2023, 7, 31)) == 2  # Ashura holidays


def test_reasons():
    assert _reason(D(2022, 10, 11), D(2022, 10, 10), -18.8, {D(2022, 10, 11)}, []).startswith(
        "ex-dividend"
    )
    # A rise on an ex-dividend date is not explained by the dividend
    assert _reason(D(2022, 10, 11), D(2022, 10, 10), 18.8, {D(2022, 10, 11)}, []) == "unexplained"
    assert _reason(D(2025, 5, 27), D(2025, 5, 26), -59.5, set(), [D(2025, 5, 29)]) == (
        "near the 2025-05-29 split"
    )
    # Two sessions can move up to 1.1^2 - 1 = 21%
    assert _reason(D(2023, 7, 31), D(2023, 7, 26), 14.5, set(), []).startswith("spans 3 sessions")
    assert _reason(D(2025, 1, 2), D(2024, 12, 31), 21.0, set(), []).startswith("spans 2")
    assert _reason(D(2025, 1, 2), D(2024, 12, 31), 25.0, set(), []) == "unexplained"
    assert _reason(D(2023, 12, 15), D(2023, 12, 14), 16.4, set(), []) == "unexplained"


def _bar(stock, day, close, volume=1000, factor=1, flag=None):
    return PricePoint(
        stock_id=stock.id,
        timestamp=datetime.datetime(day.year, day.month, day.day, tzinfo=PKT),
        close=close,
        volume=volume,
        split_factor=factor,
        quality_flag=flag,
    )


def test_outliers_use_the_served_series(db):
    stock = db.query(Stock).filter(Stock.ticker == "HBL").one()
    db.add_all(
        [
            _bar(stock, D(2023, 7, 26), 84.92),
            # Provider holiday fillers: zero volume, last close repeated
            _bar(stock, D(2023, 7, 27), 84.92, volume=0),
            _bar(stock, D(2023, 7, 28), 84.92, volume=0),
            _bar(stock, D(2023, 7, 31), 97.26),
            _bar(stock, D(2023, 8, 1), 96.65),
            _bar(stock, D(2023, 8, 2), 500.0, flag="mixed_split_level"),  # not served
            _bar(stock, D(2023, 8, 3), 550.0, factor=5),  # 110 after adjustment: +13.8%
            _bar(stock, D(2023, 8, 4), 121.0),  # exactly +10%: a limit-up day, not listed
        ]
    )
    db.add(StockSplit(stock_id=stock.id, split_date=D(2030, 1, 1), ratio=2))
    db.commit()

    outliers = find_outliers(db, stock, dividend_dates=set())
    assert [(o.day, o.move_pct, o.reason) for o in outliers] == [
        (D(2023, 7, 31), 14.5, "spans 3 sessions (2 weekday(s) without a usable bar)"),
        # The flagged bar is not served, so this move covers two sessions
        (D(2023, 8, 3), 13.8, "spans 2 sessions (1 weekday(s) without a usable bar)"),
    ]
    assert outliers[1].previous_close == 96.65 and outliers[1].close == 110.0
