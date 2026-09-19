import logging
import requests
from bs4 import BeautifulSoup
import datetime
from typing import List, Dict

from core.database import SessionLocal
from models.sentiment import NewsSentiment
from models.stock import Stock

logger = logging.getLogger(__name__)

class NewsScraperClient:
    """
    Client for scraping financial news headlines.
    Currently uses Yahoo Finance RSS feeds for reliable headline extraction.
    """
    
    @classmethod
    def fetch_headlines(cls, ticker: str) -> List[str]:
        """
        Fetch recent headlines for a given ticker.
        """
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse XML feed
            soup = BeautifulSoup(response.content, "xml")
            items = soup.find_all("item")
            
            headlines = []
            for item in items:
                title = item.find("title")
                if title and title.text:
                    headlines.append(title.text.strip())
            
            return headlines
        except Exception as e:
            logger.error(f"Error fetching news for {ticker}: {e}")
            return []

    @classmethod
    def fetch_and_save_news(cls, ticker: str) -> int:
        """
        Fetches headlines for a ticker and saves them to the DB with a mock sentiment score.
        Returns the number of headlines saved.
        """
        headlines = cls.fetch_headlines(ticker)
        if not headlines:
            logger.warning(f"No headlines found for {ticker}")
            return 0
            
        db = SessionLocal()
        try:
            # Get the stock from DB
            stock = db.query(Stock).filter(Stock.ticker == ticker).first()
            if not stock:
                logger.warning(f"Stock {ticker} not found in DB. Cannot save news.")
                return 0
                
            # We will assign a mock sentiment score of 0.0 for now.
            # In Phase 4, the ML model will update these scores or score them on insertion.
            new_sentiments = []
            for headline in headlines:
                # Avoid inserting exact duplicate headlines for the same stock
                existing = db.query(NewsSentiment).filter(
                    NewsSentiment.stock_id == stock.id,
                    NewsSentiment.headline == headline
                ).first()
                
                if not existing:
                    new_sentiments.append(
                        NewsSentiment(
                            stock_id=stock.id,
                            headline=headline,
                            sentiment_score=0.0, # Mock score
                            timestamp=datetime.datetime.utcnow()
                        )
                    )
            
            if new_sentiments:
                db.bulk_save_objects(new_sentiments)
                db.commit()
                logger.info(f"Saved {len(new_sentiments)} new headlines for {ticker}")
                
            return len(new_sentiments)
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving news to DB for {ticker}: {e}")
            return 0
        finally:
            db.close()
