from core.database import Base

from .risk_profile import RiskCategory, RiskProfile
from .user import User

# This allows alembic to import Base from models with all models attached
__all__ = ["Base", "User", "RiskCategory", "RiskProfile"]
