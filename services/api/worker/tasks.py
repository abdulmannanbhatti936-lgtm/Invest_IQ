import datetime
import logging
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert

from core.celery_app import celery_app
from core.config import settings
from core.database import SessionLocal
from integrations.market_data import MarketDataClient, MarketDataUnavailable
from integrations.psx_catalog import CATALOG_BY_TICKER
from ml.dataset import build_dataset, dataset_reference, load_dataset
from ml.inference import ModelNotFoundError, load_bundle
from ml.training import InsufficientDataError, train_and_save
from models.sentiment import NewsSentiment
from models.stock import PricePoint, Stock, StockDividend, StockSplit
from services import dividend_adjustment
from services.prediction_service import (
    InsufficientHistoryError,
    StockNotCoveredError,
    generate_prediction,
)
from services.split_adjustment import METHOD_VERSION, SUSPECT_FLAG, Split, adjust
from services.stock_service import PriceDataUnavailable, StockService

logger = logging.getLogger(__name__)

PSX_TIMEZONE = ZoneInfo("Asia/Karachi")

# Zero volume means no trades, so no new price. Yahoo emits such bars for PSX holidays and as
# placeholders for days it has no data for yet, repeating the last close; serving them would
# show a day with no change that never happened.
NO_TRADES_FLAG = "no_trades"


def _tickers(tickers: list[str] | None) -> list[str]:
    return [t.upper() for t in tickers] if tickers else settings.tracked_tickers


def upsert_price_points(db, stock: Stock, history: list[dict]) -> int:
    """Insert new days and update existing ones; never deletes older history."""
    rows = [
        {
            "stock_id": stock.id,
            "timestamp": row["timestamp"],
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row["close"],
            "volume": row.get("volume"),
        }
        for row in history
        if row.get("timestamp") and row.get("close") is not None
    ]
    if not rows:
        return 0
    stmt = insert(PricePoint).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_price_points_stock_ts",
        set_={c: stmt.excluded[c] for c in ("open", "high", "low", "close", "volume")},
    )
    db.execute(stmt)
    db.commit()
    return len(rows)


@celery_app.task(name="worker.tasks.refresh_stock_prices")
def refresh_stock_prices(
    tickers: list | None = None, period: str = "1mo", update_shares: bool = False
):
    """
    End-of-day refresh (Architecture.md §9): fetch daily OHLCV for every stock in the
    universe, upsert it into price_points and drop the cached responses of the stocks that
    changed. The API only reads the database, so a failed refresh means the "as of" date
    stops moving, never a broken page. `update_shares` also refreshes shares outstanding.
    """
    universe = [t.upper() for t in tickers] if tickers else list(CATALOG_BY_TICKER)
    db = SessionLocal()
    try:
        upserted, refreshed, no_data, failed = 0, [], [], []
        for ticker in universe:
            stock = db.query(Stock).filter(Stock.ticker == ticker).first()
            if not stock:
                logger.error(f"Price refresh skipped {ticker}: not in the stock universe")
                failed.append(ticker)
                continue
            try:
                history, splits = MarketDataClient.get_history_and_splits(ticker, period=period)
            except MarketDataUnavailable as e:
                logger.error(f"Price refresh failed for {ticker}: {e}")
                failed.append(ticker)
                continue
            if not history:
                logger.warning(f"No history returned for {ticker}")
                no_data.append(ticker)
                continue
            upserted += upsert_price_points(db, stock, history)
            record_splits(db, stock, splits)
            apply_split_adjustment(db, stock)
            if update_shares:
                _update_shares_outstanding(db, stock)
            refreshed.append(ticker)

        StockService.invalidate(refreshed)
        # yfinance reports a network failure as "no data" for each symbol (Memory.md §11), so
        # a run where nothing came back is treated as a provider outage
        status = "completed" if refreshed else "provider_unavailable"
        if not refreshed:
            logger.error(f"Price refresh got no data for any of {len(universe)} stocks")
        return {
            "status": status,
            "upserted_points": upserted,
            "refreshed": len(refreshed),
            "no_data": no_data,
            "failed": failed,
        }
    finally:
        db.close()


def record_splits(db, stock: Stock, splits: list[tuple[datetime.date, float]]) -> None:
    """Store provider split events; a later fetch with the same date updates the ratio."""
    if not splits:
        return
    stmt = insert(StockSplit).values(
        [{"stock_id": stock.id, "split_date": day, "ratio": ratio} for day, ratio in splits]
    )
    db.execute(
        stmt.on_conflict_do_update(
            constraint="uq_stock_splits_stock_date", set_={"ratio": stmt.excluded.ratio}
        )
    )
    db.commit()


def apply_split_adjustment(db, stock: Stock) -> None:
    """
    Recompute split_factor and quality_flag for all of a stock's bars from its raw closes and
    recorded splits, and store each split's decision (services/split_adjustment.py).
    Zero-volume bars are flagged and left out of the split rule.
    """
    points = (
        db.query(PricePoint)
        .filter(PricePoint.stock_id == stock.id)
        .order_by(PricePoint.timestamp)
        .all()
    )
    traded = [p for p in points if p.volume]
    splits = db.query(StockSplit).filter(StockSplit.stock_id == stock.id).all()
    result = adjust(
        [p.timestamp.astimezone(PSX_TIMEZONE).date() for p in traded],
        [float(p.close) for p in traded],
        [Split(s.split_date, float(s.ratio)) for s in splits],
    )
    for point, factor, suspect in zip(traded, result.factors, result.suspect, strict=True):
        point.split_factor = factor
        point.quality_flag = SUSPECT_FLAG if suspect else None
    # A no-trade bar keeps the factor of the last traded bar before it
    factor = 1.0
    for point in points:
        if point.volume:
            factor = point.split_factor
        else:
            point.split_factor = factor
            point.quality_flag = NO_TRADES_FLAG
        point.adjustment_version = METHOD_VERSION
    by_day = {s.split_date: s for s in splits}
    for decision in result.decisions:
        split = by_day[decision.day]
        split.history_adjusted = decision.history_adjusted_by_us
        split.decision_note = decision.note
        split.method_version = METHOD_VERSION
    db.commit()


@celery_app.task(name="worker.tasks.refresh_dividends")
def refresh_dividends(tickers: list | None = None):
    """
    Fetch every stock's dividend history, store new events and re-assess all of them
    against the served closes (services/dividend_adjustment.py). Runs after the price
    refresh, since a split re-adjustment changes the closes the decision is based on.
    """
    universe = [t.upper() for t in tickers] if tickers else list(CATALOG_BY_TICKER)
    db = SessionLocal()
    try:
        assessed, failed = [], []
        for ticker in universe:
            stock = db.query(Stock).filter(Stock.ticker == ticker).first()
            if not stock:
                failed.append(ticker)
                continue
            try:
                record_dividends(db, stock, MarketDataClient.get_dividends(ticker))
            except MarketDataUnavailable as e:
                logger.error(f"Dividend refresh failed for {ticker}: {e}")
                failed.append(ticker)
                continue
            try:
                apply_dividend_adjustment(db, stock)
            except PriceDataUnavailable:
                failed.append(ticker)
                continue
            assessed.append(ticker)
        return {"status": "completed", "assessed": len(assessed), "failed": failed}
    finally:
        db.close()


def record_dividends(db, stock: Stock, dividends: list[tuple[datetime.date, float]]) -> None:
    """Store provider dividend events; a later fetch with the same date updates the amount."""
    if not dividends:
        return
    stmt = insert(StockDividend).values(
        [{"stock_id": stock.id, "ex_date": day, "amount": amount} for day, amount in dividends]
    )
    db.execute(
        stmt.on_conflict_do_update(
            constraint="uq_stock_dividends_stock_date", set_={"amount": stmt.excluded.amount}
        )
    )
    db.commit()


def apply_dividend_adjustment(db, stock: Stock) -> None:
    """Store, per dividend, the closes around its ex-date and the factor applied (or why not)."""
    history = StockService.get_history(db, stock.ticker, period="max")
    dividends = db.query(StockDividend).filter(StockDividend.stock_id == stock.id).all()
    decisions = dividend_adjustment.assess(
        [bar["timestamp"].astimezone(PSX_TIMEZONE).date() for bar in history],
        [bar["close"] for bar in history],
        [dividend_adjustment.Dividend(d.ex_date, float(d.amount)) for d in dividends],
    )
    by_day = {d.ex_date: d for d in dividends}
    for decision in decisions:
        row = by_day[decision.day]
        row.previous_close = decision.previous_close
        row.ex_close = decision.ex_close
        row.adjustment_factor = decision.factor
        row.review_flag = decision.flag
        row.method_version = dividend_adjustment.METHOD_VERSION
    db.commit()


def _update_shares_outstanding(db, stock: Stock) -> None:
    try:
        shares = MarketDataClient.get_shares_outstanding(stock.ticker)
    except MarketDataUnavailable as e:
        logger.warning(f"Shares outstanding not refreshed for {stock.ticker}: {e}")
        return
    if shares:
        stock.shares_outstanding = shares
        db.commit()


@celery_app.task(name="worker.tasks.fetch_news_for_tickers")
def fetch_news_for_tickers(tickers: list | None = None):
    """
    Background task to fetch latest news headlines for tickers.
    """
    from integrations.news_scraper import NewsScraperClient

    total_saved = 0
    for ticker in _tickers(tickers):
        total_saved += NewsScraperClient.fetch_and_save_news(ticker)
    return {"status": "completed", "total_headlines_saved": total_saved}


@celery_app.task(name="worker.tasks.analyze_news_sentiment")
def analyze_news_sentiment():
    """
    Background task to score unscored (NULL) news headlines with FinBERT.
    """
    from ml.sentiment import sentiment_model

    db = SessionLocal()
    try:
        unscored = db.query(NewsSentiment).filter(NewsSentiment.sentiment_score.is_(None)).all()
        for news in unscored:
            news.sentiment_score = sentiment_model.analyze_headline(news.headline)
        db.commit()
        logger.info(f"Analyzed {len(unscored)} headlines.")
        return {"status": "completed", "analyzed_count": len(unscored)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="worker.tasks.train_models")
def train_models(tickers: list | None = None):
    """
    Weekly retrain (PRD.md FR15): a new dataset version from price_points and a CANDIDATE
    model with its full evaluation report (walk-forward included), both in the git-ignored
    CANDIDATE_DIR. The live model is never replaced here: latest.json changes only when a
    person promotes the candidate (ml/promote.py, Workflow.md Appendix E).
    """
    db = SessionLocal()
    try:
        dataset_path = build_dataset(db, _tickers(tickers), settings.candidate_dataset_dir)
    finally:
        db.close()
    manifest, raw = load_dataset(dataset_path)
    try:
        meta = train_and_save(raw, dataset_reference(manifest), settings.candidate_model_dir)
    except InsufficientDataError as e:
        logger.error(f"Retrain skipped: {e}")
        return {"status": "insufficient_data", "detail": str(e)}
    logger.info(f"Candidate {meta['model_version']} trained; promote with ml.promote")
    return {
        "status": "candidate",
        "model_version": meta["model_version"],
        "dataset": manifest["version"],
        "tickers": meta["tickers"],
    }


@celery_app.task(name="worker.tasks.run_predictions")
def run_predictions(tickers: list | None = None):
    """Next-day forecasts from the current model for every stock it covers."""
    try:
        bundle = load_bundle(settings.MODEL_DIR)
    except ModelNotFoundError as e:
        logger.error(f"No predictions made: {e}")
        return {"status": "no_model", "predictions_made": 0, "skipped": {}}
    db = SessionLocal()
    made, skipped = 0, {}
    try:
        for ticker in [t.upper() for t in tickers] if tickers else bundle.metadata["tickers"]:
            stock = db.query(Stock).filter(Stock.ticker == ticker).first()
            if not stock:
                skipped[ticker] = "unknown stock"
                continue
            try:
                p = generate_prediction(db, stock, bundle)
                made += 1
                logger.info(
                    f"{ticker}: {p.forecast_price} (confidence {float(p.confidence_score):.2f}), "
                    f"signal {p.signal}"
                )
            except (InsufficientHistoryError, StockNotCoveredError) as e:
                skipped[ticker] = str(e)
        return {
            "status": "completed",
            "model_version": bundle.version,
            "predictions_made": made,
            "skipped": skipped,
        }
    finally:
        db.close()
