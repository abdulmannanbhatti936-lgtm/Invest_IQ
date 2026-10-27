from core.database import Base

from .backtest import BacktestResult, IndexPoint
from .chat import ChatMessage
from .notification import AgentRun, Notification, NotificationPreference, PushDevice
from .portfolio import Portfolio, PortfolioHolding
from .prediction import Prediction
from .refresh_token import RefreshToken
from .risk_profile import RiskCategory, RiskProfile
from .sentiment import NewsSourceStatus, SentimentScore
from .stock import PricePoint, Stock, StockDividend, StockSplit
from .user import User, UserRole

# This allows alembic to import Base from models with all models attached
__all__ = [
    "Base",
    "User",
    "UserRole",
    "RefreshToken",
    "RiskCategory",
    "RiskProfile",
    "Stock",
    "PricePoint",
    "StockSplit",
    "StockDividend",
    "SentimentScore",
    "NewsSourceStatus",
    "Prediction",
    "Portfolio",
    "PortfolioHolding",
    "BacktestResult",
    "IndexPoint",
    "ChatMessage",
    "AgentRun",
    "Notification",
    "NotificationPreference",
    "PushDevice",
]
