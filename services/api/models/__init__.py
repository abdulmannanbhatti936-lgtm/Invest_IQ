from core.database import Base

from .risk_profile import RiskCategory, RiskProfile
from .user import User
from .stock import Stock, PricePoint
from .sentiment import NewsSentiment
from .prediction import Prediction

# This allows alembic to import Base from models with all models attached
__all__ = ["Base", "User", "RiskCategory", "RiskProfile", "Stock", "PricePoint", "NewsSentiment", "Prediction"]
