"""
The versioned news dataset a sentiment model is trained on (Workflow.md Step 4.6), the
counterpart of ml/dataset.py for headlines.

`<DATASET_DIR>/<version>/headlines.csv` holds one row per (stock, article) from the
training sources (Profit and Mettis): ticker, source, URL, publish time (UTC), score, label
and scorer. The headline text itself is not committed (the repository is public; the text
stays in the database and the app links to the source). The manifest records the sources,
the scorer versions, the counts and the file's SHA-256, and loading refuses a changed file.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from integrations.news.sources import TRAINING_SOURCES
from models.sentiment import SentimentScore
from models.stock import Stock

MANIFEST = "manifest.json"
FILE = "headlines.csv"
COLUMNS = ["ticker", "source", "url", "published_at", "score", "label", "scorer"]


class NewsDatasetError(ValueError):
    pass


def build_news_dataset(db: Session, tickers: list[str], dataset_dir: str | Path) -> Path:
    rows = (
        db.query(SentimentScore, Stock.ticker)
        .join(Stock, Stock.id == SentimentScore.stock_id)
        .filter(Stock.ticker.in_(tickers), SentimentScore.source.in_(TRAINING_SOURCES))
        .order_by(Stock.ticker, SentimentScore.published_at, SentimentScore.url)
        .all()
    )
    unscored = sum(row.score is None for row, _ in rows)
    if unscored:
        raise NewsDatasetError(f"{unscored} headlines are not scored yet; run the scoring first")
    frame = pd.DataFrame(
        [
            {
                "ticker": ticker,
                "source": row.source,
                "url": row.url,
                "published_at": row.published_at.astimezone(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "score": float(row.score),
                "label": row.label,
                "scorer": row.scorer,
            }
            for row, ticker in rows
        ],
        columns=COLUMNS,
    )
    last_day = frame["published_at"].max()[:10] if len(frame) else "empty"
    version = f"news{len(tickers)}-{last_day}"
    out = Path(dataset_dir) / version
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / FILE, index=False, float_format="%.4f", lineterminator="\n")

    versions = sorted({row.scorer_version for row, _ in rows})
    manifest = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sources": list(TRAINING_SOURCES),
        "collection": "Memory.md §3 (2026-10-11): slug-matched articles, polite scraping",
        "scorer_versions": versions,
        "rows": len(frame),
        "first_published_at": frame["published_at"].min() if len(frame) else None,
        "last_published_at": frame["published_at"].max() if len(frame) else None,
        "rows_per_ticker": {t: int((frame["ticker"] == t).sum()) for t in tickers},
        "rows_per_source": {s: int((frame["source"] == s).sum()) for s in TRAINING_SOURCES},
        "rows_per_scorer": frame["scorer"].value_counts().to_dict(),
        "sha256": hashlib.sha256((out / FILE).read_bytes()).hexdigest(),
    }
    (out / MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return out


def load_news_dataset(path: str | Path) -> tuple[dict, dict[str, pd.DataFrame]]:
    """The manifest and, per ticker, a frame of `published_at` (UTC) and `score`."""
    root = Path(path)
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    if hashlib.sha256((root / FILE).read_bytes()).hexdigest() != manifest["sha256"]:
        raise NewsDatasetError(f"{root / FILE} does not match the manifest hash")
    frame = pd.read_csv(root / FILE)
    frame["published_at"] = pd.to_datetime(frame["published_at"], utc=True)
    return manifest, {
        ticker: group[["published_at", "score"]].reset_index(drop=True)
        for ticker, group in frame.groupby("ticker")
    }


def news_reference(manifest: dict) -> dict:
    """What a model stores about its news input."""
    return {
        "version": manifest["version"],
        "sources": manifest["sources"],
        "sha256": manifest["sha256"],
        "scorer_versions": manifest["scorer_versions"],
    }
