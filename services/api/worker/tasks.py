import datetime
import logging

from core.celery_app import celery_app
from core.database import SessionLocal
from integrations.market_data import MarketDataClient
from ml.sentiment import sentiment_model
from ml.lstm_predictor import lstm_predictor
from ml.features import FeatureEngineer
from models.sentiment import NewsSentiment
from models.stock import PricePoint, Stock
from models.prediction import Prediction

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

@celery_app.task(name="worker.tasks.run_predictions")
def run_predictions(tickers: list = None):
    """
    Background task to run LSTM predictions for stocks and save to DB.
    """
    if not tickers:
        tickers = DEFAULT_TICKERS
        
    db = SessionLocal()
    try:
        predictions_made = 0
        for ticker_symbol in tickers:
            logger.info(f"Running predictions for {ticker_symbol}")
            stock = db.query(Stock).filter(Stock.ticker == ticker_symbol).first()
            if not stock:
                continue
                
            # Get historical prices and sentiment
            price_points = db.query(PricePoint).filter(PricePoint.stock_id == stock.id).order_by(PricePoint.timestamp.asc()).all()
            sentiments = db.query(NewsSentiment).filter(NewsSentiment.stock_id == stock.id).all()
            
            # Prepare feature data
            df = FeatureEngineer.prepare_training_data(price_points, sentiments)
            if df.empty:
                logger.warning(f"Not enough data to run predictions for {ticker_symbol}")
                continue
                
            # For demonstration in FYP, we train the model on the fly if not trained
            # In a real app, training is a separate heavy job.
            if lstm_predictor.model is None:
                success, rmse = lstm_predictor.train(df)
                if not success:
                    continue
                    
            predicted_price, confidence, direction = lstm_predictor.predict_latest(df)
            
            if predicted_price > 0:
                prediction_record = Prediction(
                    stock_id=stock.id,
                    predicted_price=predicted_price,
                    signal=direction,
                    confidence_score=confidence,
                    model_version="v1.0-lstm-advanced"
                )
                db.add(prediction_record)
                db.commit()
                predictions_made += 1
                logger.info(f"Saved prediction for {ticker_symbol}: {direction} (Confidence: {confidence:.2f})")
                
        return {"status": "completed", "predictions_made": predictions_made}
    except Exception as e:
        db.rollback()
        logger.error(f"Error in run_predictions: {e}")
        raise e
    finally:
        db.close()
