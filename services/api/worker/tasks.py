import logging
from core.celery_app import celery_app
from core.database import SessionLocal
from models.stock import Stock, PricePoint
from models.sentiment import NewsSentiment
from integrations.market_data import MarketDataClient
from ml.sentiment import sentiment_model
from sqlalchemy.exc import IntegrityError
import datetime

logger = logging.getLogger(__name__)

# List of important tickers to pre-fetch. We include AAPL, SYS to ensure Yahoo has data.
DEFAULT_TICKERS = ["AAPL", "SYS"]

@celery_app.task(name="worker.tasks.fetch_market_data_for_tickers")
def fetch_market_data_for_tickers(tickers: list = None, period: str = "1y"):
    """
    Background task to fetch market data and bulk save to DB.
    """
    if not tickers:
        tickers = DEFAULT_TICKERS
        
    db = SessionLocal()
    try:
        inserted_count = 0
        for ticker_symbol in tickers:
            logger.info(f"Fetching bulk history for {ticker_symbol} over period {period}")
            
            # Ensure stock exists in DB
            stock = db.query(Stock).filter(Stock.ticker == ticker_symbol).first()
            if not stock:
                logger.info(f"Stock {ticker_symbol} not found in DB. Creating it.")
                # We fetch a quick quote just to get the name/sector if possible
                quote = MarketDataClient.get_quote(ticker_symbol)
                name = quote.get("name", ticker_symbol) if quote else ticker_symbol
                sector = quote.get("sector") if quote else None
                
                stock = Stock(ticker=ticker_symbol, name=name, sector=sector)
                db.add(stock)
                db.commit()
                db.refresh(stock)
            
            # Fetch history
            history = MarketDataClient.get_history(ticker_symbol, period=period)
            if not history:
                logger.warning(f"No history found for {ticker_symbol}")
                continue
                
            # Prepare bulk insert objects
            new_price_points = []
            for row in history:
                timestamp = row.get("timestamp")
                if not timestamp:
                    continue
                    
                # Ensure it's a date or datetime
                if isinstance(timestamp, str):
                    timestamp = datetime.datetime.fromisoformat(timestamp)
                    
                new_price_points.append(
                    PricePoint(
                        stock_id=stock.id,
                        timestamp=timestamp,
                        open=row.get("open"),
                        high=row.get("high"),
                        low=row.get("low"),
                        close=row.get("close"),
                        volume=row.get("volume")
                    )
                )
            
            if new_price_points:
                db.query(PricePoint).filter(PricePoint.stock_id == stock.id).delete()
                
                logger.info(f"Bulk saving {len(new_price_points)} price points for {ticker_symbol}")
                db.bulk_save_objects(new_price_points)
                db.commit()
                inserted_count += len(new_price_points)
                
        return {"status": "completed", "inserted_points": inserted_count}
    except Exception as e:
        db.rollback()
        logger.error(f"Error in fetch_market_data_for_tickers: {e}")
        raise e
    finally:
        db.close()

@celery_app.task(name="worker.tasks.fetch_news_for_tickers")
def fetch_news_for_tickers(tickers: list = None):
    """
    Background task to fetch latest news headlines for tickers.
    """
    from integrations.news_scraper import NewsScraperClient
    if not tickers:
        tickers = DEFAULT_TICKERS
        
    total_saved = 0
    for ticker_symbol in tickers:
        logger.info(f"Fetching news for {ticker_symbol}")
        count = NewsScraperClient.fetch_and_save_news(ticker_symbol)
        total_saved += count
        
    return {"status": "completed", "total_headlines_saved": total_saved}

@celery_app.task(name="worker.tasks.analyze_news_sentiment")
def analyze_news_sentiment():
    """
    Background task to analyze the sentiment of unscored news headlines using AI.
    """
    db = SessionLocal()
    try:
        # Find all un-analyzed headlines (score exactly 0.0 is our un-analyzed default)
        unscored_news = db.query(NewsSentiment).filter(NewsSentiment.sentiment_score == 0.0).all()
        
        if not unscored_news:
            logger.info("No unscored news found.")
            return {"status": "completed", "analyzed_count": 0}
            
        logger.info(f"Found {len(unscored_news)} unscored headlines. Analyzing...")
        
        analyzed_count = 0
        for news in unscored_news:
            score = sentiment_model.analyze_headline(news.headline)
            news.sentiment_score = score
            analyzed_count += 1
            
        db.commit()
        logger.info(f"Successfully analyzed {analyzed_count} headlines.")
        return {"status": "completed", "analyzed_count": analyzed_count}
    except Exception as e:
        db.rollback()
        logger.error(f"Error analyzing news sentiment: {e}")
        raise e
    finally:
        db.close()
