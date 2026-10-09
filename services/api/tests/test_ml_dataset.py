import datetime

import pytest

from ml.dataset import DatasetError, build_dataset, dividend_adjusted, load_dataset, served_frame
from models.stock import StockDividend
from tests.test_stocks import bar, store

D = datetime.date


@pytest.fixture
def sys_history(db, fake_redis):
    """SYS: a 2:1 split-adjusted bar, a flagged bar and an applied Rs.5 dividend."""
    bars = [
        bar(D(2026, 3, 2), 220.0) | {"split_factor": 2},
        bar(D(2026, 3, 3), 104.0) | {"quality_flag": "mixed_split_level"},
        bar(D(2026, 3, 4), 100.0),
        bar(D(2026, 3, 5), 96.0),
    ]
    stock = store(db, "SYS", bars)
    db.add(
        StockDividend(stock_id=stock.id, ex_date=D(2026, 3, 5), amount=5, adjustment_factor=0.95)
    )
    db.add(
        StockDividend(
            stock_id=stock.id, ex_date=D(2026, 3, 4), amount=1, review_flag="drop_mismatch"
        )
    )
    db.commit()
    return stock


def test_served_frame_uses_served_bars_and_applied_dividends(db, sys_history):
    frame = served_frame(db, sys_history)
    # Flagged bar left out, split factor applied, dates are PSX trading dates
    assert [d.date() for d in frame["date"]] == [D(2026, 3, 2), D(2026, 3, 4), D(2026, 3, 5)]
    assert frame["close"].tolist() == [110.0, 100.0, 96.0]
    # Only the applied dividend counts; the held-back one does not
    assert frame["dividend_factor"].tolist() == pytest.approx([0.95, 0.95, 1.0])
    adjusted = dividend_adjusted(frame)
    assert adjusted["close"].tolist() == pytest.approx([104.5, 95.0, 96.0])
    assert adjusted["volume"].tolist() == frame["volume"].tolist()


def test_dataset_round_trip_and_hash_check(db, sys_history, tmp_path):
    path = build_dataset(db, ["SYS"], tmp_path)
    assert path.name == "psx1-2026-03-05"
    manifest, frames = load_dataset(path)
    entry = manifest["tickers"]["SYS"]
    assert entry["rows"] == 3 and entry["dividends_applied"] == 1
    assert entry["dividends_held_back"] == [
        {"ex_date": "2026-03-04", "amount": 1.0, "flag": "drop_mismatch"}
    ]
    assert frames["SYS"]["close"].tolist() == [110.0, 100.0, 96.0]

    csv = path / "SYS.csv"
    csv.write_text(csv.read_text().replace("96.0", "97.0"))
    with pytest.raises(DatasetError):
        load_dataset(path)


def test_unknown_ticker_is_refused(db, tmp_path):
    with pytest.raises(DatasetError):
        build_dataset(db, ["NOSUCH"], tmp_path)
