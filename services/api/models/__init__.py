from core.database import Base

from .prediction import Prediction
from .risk_profile import RiskCategory, RiskProfile
from .sentiment import NewsSentiment
from .stock import PricePoint, Stock
from .user import User, UserRole

# This allows alembic to import Base from models with all models attached
__all__ = [
    "Base",
    "User",
    "UserRole",
    "RiskCategory",
    "RiskProfile",
    "Stock",
    "PricePoint",
    "NewsSentiment",
    "Prediction",
]
