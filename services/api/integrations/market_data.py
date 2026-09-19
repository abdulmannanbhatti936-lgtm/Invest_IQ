import yfinance as yf
from typing import List, Dict, Any, Optional
import datetime
import logging

logger = logging.getLogger(__name__)

class MarketDataClient:
    """
    Isolated client wrapper for fetching market data.
    Currently wraps Yahoo Finance, but can be swapped out for official PSX APIs later.
    """
    
    @staticmethod
    def _format_ticker(ticker: str) -> str:
        """
        Format the ticker for Yahoo Finance.
        PSX tickers often use .KA suffix (e.g., SYS.KA), but we allow
        the caller to pass the exact Yahoo Finance ticker symbol.
        """
        return ticker.upper().strip()
        
    @classmethod
    def get_quote(cls, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest quote and basic info for a given ticker.
        """
        try:
            formatted_ticker = cls._format_ticker(ticker)
            stock = yf.Ticker(formatted_ticker)
            
            # yfinance history is the most reliable way to get current price
            hist = stock.history(period="1d")
            
            if hist.empty:
                logger.warning(f"No price data found for {formatted_ticker}")
                return None
                
            info = stock.info
            latest_data = hist.iloc[-1]
            
            return {
                "ticker": ticker.upper(),
                "name": info.get("shortName", ticker.upper()),
                "sector": info.get("sector", "Unknown"),
                "price": float(latest_data["Close"]),
                "volume": int(latest_data["Volume"]),
                "timestamp": hist.index[-1].to_pydatetime()
            }
        except Exception as e:
            logger.error(f"Error fetching quote for {ticker}: {str(e)}")
            return None

    @classmethod
    def get_history(cls, ticker: str, period: str = "1y", start: Optional[datetime.date] = None, end: Optional[datetime.date] = None) -> List[Dict[str, Any]]:
        """
        Get historical OHLCV data for a given ticker.
        """
        try:
            formatted_ticker = cls._format_ticker(ticker)
            stock = yf.Ticker(formatted_ticker)
            
            kwargs = {}
            if start:
                kwargs["start"] = start.strftime("%Y-%m-%d")
            if end:
                kwargs["end"] = end.strftime("%Y-%m-%d")
            if not start and not end:
                kwargs["period"] = period
                
            hist = stock.history(**kwargs)
            
            if hist.empty:
                return []
                
            results = []
            for index, row in hist.iterrows():
                results.append({
                    "timestamp": index.to_pydatetime(),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"])
                })
                
            return results
        except Exception as e:
            logger.error(f"Error fetching history for {ticker}: {str(e)}")
            return []
