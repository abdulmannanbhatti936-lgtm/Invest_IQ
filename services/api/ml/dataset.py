"""
Training series and the versioned training dataset (Workflow.md Step 3.1).

The model's series is built from the same bars the app serves (split-adjusted, flagged bars
left out; services/stock_service.py) and then dividend-adjusted backwards
(services/dividend_adjustment.py). Training, evaluation and live inference all go through
`served_frame` + `dividend_adjusted`, so the model always sees one kind of series.

A dataset is a folder `<DATASET_DIR>/<version>/` holding one CSV per ticker and a manifest
with the source, methods, date range and a SHA-256 per file, so a training run can name
exactly what it was trained on and refuse a file that has changed since.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from ml.features import price_points_to_frame
from models.stock import Stock, StockDividend
from services import dividend_adjustment, split_adjustment
from services.stock_service import StockService

MANIFEST = "manifest.json"
CSV_COLUMNS = ["date", "open", "high", "low", "close", "volume", "dividend_factor"]
PRICE_COLUMNS = ["open", "high", "low", "close"]


class DatasetError(ValueError):
    pass


def served_frame(db: Session, stock: Stock) -> pd.DataFrame:
    """Served bars (PSX trading dates, split-adjusted) plus each bar's dividend factor."""
    frame = price_points_to_frame(StockService.get_history(db, stock.ticker, period="max"))
    applied = [
        (d.ex_date, float(d.adjustment_factor))
        for d in db.query(StockDividend).filter(
            StockDividend.stock_id == stock.id, StockDividend.adjustment_factor.isnot(None)
        )
    ]
    frame["dividend_factor"] = dividend_adjustment.cumulative_factors(
        [day.date() for day in frame["date"]], applied
    )
    return frame


def dividend_adjusted(frame: pd.DataFrame) -> pd.DataFrame:
    """The model's input series: prices times the dividend factor (volume is unchanged)."""
    out = frame.copy()
    for col in PRICE_COLUMNS:
        out[col] = out[col] * out["dividend_factor"]
    return out


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_dataset(db: Session, tickers: list[str], dataset_dir: str | Path) -> Path:
    """Write one CSV per ticker plus the manifest; the version is the last bar's date."""
    frames = {}
    for ticker in tickers:
        stock = db.query(Stock).filter(Stock.ticker == ticker.upper()).first()
        if stock is None:
            raise DatasetError(f"{ticker} is not in the stock universe")
        frames[stock.ticker] = (stock, served_frame(db, stock))

    last_day = max(frame["date"].max() for _, frame in frames.values()).date()
    version = f"psx{len(frames)}-{last_day.isoformat()}"
    out = Path(dataset_dir) / version
    out.mkdir(parents=True, exist_ok=True)

    entries = {}
    for ticker, (stock, frame) in frames.items():
        path = out / f"{ticker}.csv"
        frame.assign(
            date=frame["date"].dt.strftime("%Y-%m-%d"),
            volume=frame["volume"].round().astype("int64"),
        )[CSV_COLUMNS].to_csv(path, index=False, float_format="%.6f", lineterminator="\n")
        dividends = db.query(StockDividend).filter(StockDividend.stock_id == stock.id).all()
        in_range = [d for d in dividends if frame["date"].iloc[0].date() < d.ex_date <= last_day]
        entries[ticker] = {
            "sector": stock.sector,
            "rows": len(frame),
            "date_start": frame["date"].iloc[0].date().isoformat(),
            "date_end": frame["date"].iloc[-1].date().isoformat(),
            "dividends_in_range": len(in_range),
            "dividends_applied": sum(d.adjustment_factor is not None for d in in_range),
            "dividends_held_back": [
                {"ex_date": d.ex_date.isoformat(), "amount": float(d.amount), "flag": d.review_flag}
                for d in sorted(in_range, key=lambda d: d.ex_date)
                if d.adjustment_factor is None
            ],
            "sha256": _sha256(path),
        }

    manifest = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "price_points (Yahoo Finance .KA daily bars, auto_adjust=False)",
        "series": "served bars: split-adjusted, quality-flagged bars excluded",
        "split_method": split_adjustment.METHOD_VERSION,
        "dividend_method": dividend_adjustment.METHOD_VERSION,
        "columns": {
            "open/high/low/close/volume": "as served (not dividend-adjusted)",
            "dividend_factor": "multiply prices by this for the model's series",
        },
        "tickers": entries,
    }
    (out / MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return out


def load_dataset(path: str | Path) -> tuple[dict, dict[str, pd.DataFrame]]:
    """Read a dataset folder; refuses any CSV whose hash differs from the manifest."""
    root = Path(path)
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    frames = {}
    for ticker, entry in manifest["tickers"].items():
        csv = root / f"{ticker}.csv"
        if _sha256(csv) != entry["sha256"]:
            raise DatasetError(f"{csv} does not match the manifest hash")
        frame = pd.read_csv(csv)
        frame["date"] = pd.to_datetime(frame["date"])
        frames[ticker] = frame
    return manifest, frames


def main() -> None:
    """`python -m ml.dataset`: build a new dataset version for the tracked tickers."""
    from core.config import settings
    from core.database import SessionLocal

    db = SessionLocal()
    try:
        path = build_dataset(db, settings.tracked_tickers, settings.DATASET_DIR)
    finally:
        db.close()
    print(f"Dataset written to {path}")


if __name__ == "__main__":
    main()
