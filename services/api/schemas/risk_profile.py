from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from models.risk_profile import RiskCategory

class RiskProfileBase(BaseModel):
    answers: dict

class RiskProfileUpdate(RiskProfileBase):
    pass

class RiskProfileCreate(RiskProfileBase):
    pass

class RiskProfile(RiskProfileBase):
    id: UUID
    user_id: UUID
    category: RiskCategory
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
