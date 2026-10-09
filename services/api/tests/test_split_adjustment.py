"""
Split adjustment (services/split_adjustment.py) on fixtures shaped like the real Yahoo PSX
history: unadjusted history before a recent split, a window where Yahoo mixes the two price
levels bar by bar, and older splits that Yahoo already adjusted.
"""

import datetime

import pytest

from core.deps import get_current_user
from main import app
from models.stock import PricePoint, Stock, StockSplit
from services.split_adjustment import METHOD_VERSION, MIXED_WINDOW, SUSPECT_FLAG, Split, adjust
from worker.tasks import apply_split_adjustment, record_splits

PKT = datetime.timezone(datetime.timedelta(hours=5))


def trading_days(start: datetime.date, count: int) -> list[datetime.date]:
    days, day = [], start
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day += datetime.timedelta(days=1)
    return days


def drift(start: float, count: int, step: float = 0.002) -> list[float]:
    """A gently moving price series (+0.2% then -0.2% per day, alternating)."""
    prices, price = [], start
    for i in range(count):
        price *= 1 + (step if i % 2 == 0 else -step)
        prices.append(round(price, 2))
    return prices


# LUCK, 5:1 split listed on 2025-04-21. Before the mixed window Yahoo returns the real
# (unadjusted) prices near Rs.1,450; after the split the level is near Rs.300; inside the
# window bars flip between the two levels (real sequence: 1456, 292, 1412, 1560, 320).
LUCK_SPLIT = datetime.date(2025, 4, 21)
LUCK_FLIP = [1456.28, 291.99, 1412.72, 1560.98, 320.37]


def luck_series() -> tuple[list[datetime.date], list[float]]:
    after = trading_days(LUCK_SPLIT, 20)
    before = [
        d for d in trading_days(LUCK_SPLIT - datetime.timedelta(days=200), 200) if d < LUCK_SPLIT
    ]
    window = before[-MIXED_WINDOW:]
    history = before[:-MIXED_WINDOW][-60:]
    closes = drift(1450.0, len(history))
    # Inside the window: the real flip first, then alternating levels around Rs.300 x 5
    mixed = list(LUCK_FLIP)
    level = 300.0
    while len(mixed) < len(window):
        level *= 1.001
        mixed.append(round(level * (5 if len(mixed) % 3 else 1), 2))
    mixed[-3:] = [312.0, 1555.0, 311.0]
    return history + window + after, closes + mixed + drift(310.0, len(after))


def test_luck_five_for_one_split_with_mixed_window():
    days, closes = luck_series()
    result = adjust(days, closes, [Split(LUCK_SPLIT, 5.0)])
    adjusted = [c / f for c, f in zip(closes, result.factors, strict=True)]

    assert not any(result.suspect)
    # One continuous series at the post-split level: no day moves more than ~10%
    moves = [abs(adjusted[i] / adjusted[i - 1] - 1) for i in range(1, len(adjusted))]
    assert max(moves) < 0.11
    # The real flip resolves to one level: 1456/5, 292, 1412/5, 1560/5, 320
    window_start = len(days) - 20 - MIXED_WINDOW
    flip = adjusted[window_start : window_start + 5]
    assert flip == pytest.approx([291.256, 291.99, 282.544, 312.196, 320.37], rel=1e-4)
    # Deterministic part: every bar before the window is divided by the ratio
    assert set(result.factors[:window_start]) == {5.0}
    assert set(result.factors[-20:]) == {1.0}
    (decision,) = result.decisions
    assert decision.history_adjusted_by_us and "not adjusted by the provider" in decision.note


def test_two_splits_one_already_adjusted_by_the_provider():
    # SYS: 2:1 in 2022 already reflected by Yahoo (continuous series), 5:1 in 2025 not
    old_split, new_split = datetime.date(2022, 3, 31), datetime.date(2025, 5, 29)
    days = trading_days(datetime.date(2022, 1, 3), 900)
    i_new = next(i for i, d in enumerate(days) if d >= new_split)
    closes = drift(350.0, i_new) + drift(108.0, len(days) - i_new)
    # Unadjusted before the 2025 split, with two already-adjusted bars inside its window
    closes[i_new - 10] = round(closes[i_new - 10] / 5, 2)
    closes[i_new - 4] = round(closes[i_new - 4] / 5, 2)
    for i in range(i_new):
        closes[i] = round(closes[i] * 1.55, 2)  # pre-split level about 540

    result = adjust(days, closes, [Split(old_split, 2.0), Split(new_split, 5.0)])
    decisions = {d.day: d for d in result.decisions}
    assert decisions[old_split].history_adjusted_by_us is False
    assert decisions[old_split].note == "continuous across the split"
    assert decisions[new_split].history_adjusted_by_us is True
    # Bars before both splits are divided by 5 only, never by 2 x 5
    assert result.factors[0] == 5.0
    assert result.factors[i_new - 10] == 1.0 and result.factors[i_new - 4] == 1.0
    assert result.factors[i_new - 9] == 5.0


def test_two_unadjusted_splits_compound():
    first, second = datetime.date(2024, 3, 1), datetime.date(2025, 3, 3)
    days = trading_days(datetime.date(2023, 6, 1), 600)
    i1 = next(i for i, d in enumerate(days) if d >= first)
    i2 = next(i for i, d in enumerate(days) if d >= second)
    closes = drift(1000.0, i1) + drift(500.0, i2 - i1) + drift(100.0, len(days) - i2)

    result = adjust(days, closes, [Split(first, 2.0), Split(second, 5.0)])
    assert result.factors[0] == 10.0
    assert result.factors[i1] == 5.0 and result.factors[i2] == 1.0
    assert all(d.history_adjusted_by_us for d in result.decisions)


def test_stock_without_splits_is_unchanged():
    days = trading_days(datetime.date(2024, 1, 1), 300)
    closes = drift(120.0, 300, step=0.03)
    result = adjust(days, closes, [])
    assert result.factors == [1.0] * 300 and not any(result.suspect) and result.decisions == []


def test_bar_at_neither_level_is_flagged_not_guessed():
    # SYS 2025: some bars sat at half the pre-split level (Rs.270), matching neither reading
    days, closes = luck_series()
    window_start = len(days) - 20 - MIXED_WINDOW
    closes[window_start + 20] = 725.0  # ~2.5x the adjusted level
    result = adjust(days, closes, [Split(LUCK_SPLIT, 5.0)])
    assert result.suspect[window_start + 20]
    assert sum(result.suspect) == 1
    assert closes[window_start + 20] == 725.0  # the raw value itself is not touched


# ---- Stored data and the API


@pytest.fixture
def authenticated():
    app.dependency_overrides[get_current_user] = lambda: object()
    yield
    app.dependency_overrides.clear()


def _store_luck(db) -> Stock:
    stock = db.query(Stock).filter(Stock.ticker == "LUCK").one()
    days, closes = luck_series()
    db.add_all(
        PricePoint(
            stock_id=stock.id,
            timestamp=datetime.datetime(d.year, d.month, d.day, tzinfo=PKT),
            open=c,
            high=c,
            low=c,
            close=c,
            volume=1_000,
        )
        for d, c in zip(days, closes, strict=True)
    )
    db.commit()
    return stock


def test_job_stores_factors_and_decisions_and_keeps_raw(db):
    stock = _store_luck(db)
    raw_before = sorted(float(p.close) for p in stock.price_points)

    record_splits(db, stock, [(LUCK_SPLIT, 5.0)])
    apply_split_adjustment(db, stock)
    db.expire_all()

    points = db.query(PricePoint).filter(PricePoint.stock_id == stock.id).all()
    assert sorted(float(p.close) for p in points) == raw_before
    assert {p.adjustment_version for p in points} == {METHOD_VERSION}
    assert {float(p.split_factor) for p in points} == {1.0, 5.0}
    assert not [p for p in points if p.quality_flag == SUSPECT_FLAG]
    split = db.query(StockSplit).filter(StockSplit.stock_id == stock.id).one()
    assert split.history_adjusted is True and split.method_version == METHOD_VERSION


def test_api_serves_adjusted_prices_and_scaled_volume(client, db, fake_redis, authenticated):
    stock = _store_luck(db)
    record_splits(db, stock, [(LUCK_SPLIT, 5.0)])
    apply_split_adjustment(db, stock)

    history = client.get("/stocks/LUCK/history?period=max").json()
    first = history[0]
    assert first["close"] == pytest.approx(1450.0 * 1.002 / 5, rel=1e-3)
    assert first["volume"] == 5_000  # 1,000 old shares are 5,000 new shares
    assert history[-1]["volume"] == 1_000
    moves = [abs(history[i]["close"] / history[i - 1]["close"] - 1) for i in range(1, len(history))]
    assert max(moves) < 0.11


def test_api_leaves_out_flagged_bars(client, db, fake_redis, authenticated):
    stock = _store_luck(db)
    points = db.query(PricePoint).filter(PricePoint.stock_id == stock.id).all()
    points[10].quality_flag = SUSPECT_FLAG
    db.commit()
    history = client.get("/stocks/LUCK/history?period=max").json()
    assert len(history) == len(points) - 1
