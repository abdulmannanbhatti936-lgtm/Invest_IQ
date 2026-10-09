import logging

from sqlalchemy.dialects.postgresql import insert

from core.celery_app import celery_app
from core.config import settings
from core.database import SessionLocal
from integrations.market_data import MarketDataClient
from integrations.psx_catalog import CATALOG_BY_TICKER
from ml.features import price_points_to_frame
from ml.inference import ModelNotFoundError
from ml.training import InsufficientDataError, new_model_version, train_ticker
from models.sentiment import NewsSentiment
from models.stock import PricePoint, Stock
from services.prediction_service import InsufficientHistoryError, generate_prediction

logger = logging.getLogger(__name__)


def _tickers(tickers: list[str] | None) -> list[str]:
    return [t.upper() for t in tickers] if tickers else settings.tracked_tickers


def _get_or_create_stock(db, ticker: str) -> Stock:
    stock = db.query(Stock).filter(Stock.ticker == ticker).first()
    if stock:
        return stock
    name, sector = CATALOG_BY_TICKER.get(ticker, (ticker, None))
    stock = Stock(ticker=ticker, name=name, sector=sector)
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


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
def refresh_stock_prices(tickers: list | None = None, period: str = "5y"):
    """
    Fetch daily OHLCV for tracked tickers and upsert into price_points
    (Architecture.md §9). A provider failure for one ticker is logged and skipped.
    """
    db = SessionLocal()
    try:
        upserted, failed = 0, []
        for ticker in _tickers(tickers):
            try:
                history = MarketDataClient.get_history(ticker, period=period)
            except Exception as e:
                logger.error(f"Price refresh failed for {ticker}: {e}")
                failed.append(ticker)
                continue
            if not history:
                logger.warning(f"No history found for {ticker}")
                failed.append(ticker)
                continue
            stock = _get_or_create_stock(db, ticker)
            upserted += upsert_price_points(db, stock, history)
        return {"status": "completed", "upserted_points": upserted, "failed": failed}
    finally:
        db.close()


# Kept so anything still calling the old task name keeps working
fetch_market_data_for_tickers = celery_app.task(name="worker.tasks.fetch_market_data_for_tickers")(
    refresh_stock_prices.run
)


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
