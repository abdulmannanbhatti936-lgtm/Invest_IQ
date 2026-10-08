"""
Versioned raw training dataset (Workflow.md Step 3.1): one CSV of daily OHLCV
per PSX ticker plus a manifest describing source, date range and row counts.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from integrations.market_data import MarketDataClient

MANIFEST = "manifest.json"


def download_dataset(tickers: list[str], dataset_dir: str | Path, period: str = "5y") -> dict:
    out = Path(dataset_dir)
    out.mkdir(parents=True, exist_ok=True)
    entries = {}
    for ticker in tickers:
        history = MarketDataClient.get_history(ticker, period=period)
        if not history:
            entries[ticker] = {"rows": 0, "error": "no data from provider"}
            continue
        df = pd.DataFrame(history).rename(columns={"timestamp": "date"})
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df.to_csv(out / f"{ticker}.csv", index=False)
        entries[ticker] = {
            "rows": len(df),
            "date_start": df["date"].iloc[0],
            "date_end": df["date"].iloc[-1],
            "provider_symbol": MarketDataClient.to_provider_symbol(ticker),
        }
    manifest = {
        "source": "Yahoo Finance via yfinance (PSX symbols with .KA suffix), daily OHLCV",
        "price_adjustment": "yfinance default (auto_adjust=True: split/dividend-adjusted)",
        "period": period,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "tickers": entries,
    }
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2))
    return manifest


def load_ticker_csv(ticker: str, dataset_dir: str | Path) -> pd.DataFrame:
    path = Path(dataset_dir) / f"{ticker.upper()}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run `python -m ml.train --download` first")
    return pd.read_csv(path)
