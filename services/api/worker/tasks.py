import logging

from sqlalchemy.dialects.postgresql import insert

from core.celery_app import celery_app
from core.config import settings
from core.database import SessionLocal
from integrations.market_data import MarketDataClient, MarketDataUnavailable
from integrations.psx_catalog import CATALOG_BY_TICKER
from ml.features import price_points_to_frame
from ml.inference import ModelNotFoundError
from ml.training import InsufficientDataError, new_model_version, train_ticker
from models.sentiment import NewsSentiment
from models.stock import PricePoint, Stock
from services.prediction_service import InsufficientHistoryError, generate_prediction
from services.stock_service import StockService

logger = logging.getLogger(__name__)


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
                history = MarketDataClient.get_history(ticker, period=period)
            except MarketDataUnavailable as e:
                logger.error(f"Price refresh failed for {ticker}: {e}")
                failed.append(ticker)
                continue
            if not history:
                logger.warning(f"No history returned for {ticker}")
                no_data.append(ticker)
                continue
            upserted += upsert_price_points(db, stock, history)
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
    Retrain LSTM + classifiers for each ticker from the price_points table
    (PRD.md FR15: schedulable retraining). Saves a new model_version.
    """
    db = SessionLocal()
    version = new_model_version()
    trained, skipped = [], []
    try:
        for ticker in _tickers(tickers):
            stock = db.query(Stock).filter(Stock.ticker == ticker).first()
            if not stock:
                skipped.append(ticker)
                continue
            points = (
                db.query(PricePoint)
                .filter(PricePoint.stock_id == stock.id)
                .order_by(PricePoint.timestamp.asc())
                .all()
            )
            try:
                train_ticker(
                    ticker, price_points_to_frame(points), settings.MODEL_DIR, version=version
                )
                trained.append(ticker)
            except InsufficientDataError as e:
                logger.warning(str(e))
                skipped.append(ticker)
        return {
            "status": "completed",
            "model_version": version,
            "trained": trained,
            "skipped": skipped,
        }
    finally:
        db.close()


@celery_app.task(name="worker.tasks.run_predictions")
def run_predictions(tickers: list | None = None):
    """
    Generate next-day predictions from the latest saved models and store them.
    """
    db = SessionLocal()
    made, skipped = 0, {}
    try:
        for ticker in _tickers(tickers):
            stock = db.query(Stock).filter(Stock.ticker == ticker).first()
            if not stock:
                skipped[ticker] = "unknown stock"
                continue
            try:
                p = generate_prediction(db, stock)
                made += 1
                logger.info(
                    f"{ticker}: {p.signal} ({float(p.confidence_score):.2f}) -> {p.forecast_price}"
                )
            except InsufficientHistoryError as e:
                skipped[ticker] = str(e)
            except ModelNotFoundError as e:
                skipped[ticker] = str(e)
        return {"status": "completed", "predictions_made": made, "skipped": skipped}
    finally:
        db.close()
