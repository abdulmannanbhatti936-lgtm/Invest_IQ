from sqlalchemy.orm import Session
from models.risk_profile import RiskProfile
from schemas.risk_profile import RiskProfileCreate, RiskProfileUpdate
from services.risk_scoring import calculate_risk_category
from uuid import UUID

def get_risk_profile_by_user(db: Session, user_id: UUID) -> RiskProfile | None:
    return db.query(RiskProfile).filter(RiskProfile.user_id == user_id).first()

def create_risk_profile(db: Session, user_id: UUID, profile_in: RiskProfileCreate) -> RiskProfile:
    category = calculate_risk_category(profile_in.answers)
    
    db_profile = RiskProfile(
        user_id=user_id,
        category=category,
        answers=profile_in.answers
    )
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile

def update_risk_profile(db: Session, db_profile: RiskProfile, profile_in: RiskProfileUpdate) -> RiskProfile:
    category = calculate_risk_category(profile_in.answers)
    
    db_profile.answers = profile_in.answers
    db_profile.category = category
    db.commit()
    db.refresh(db_profile)
    return db_profile
