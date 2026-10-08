from uuid import UUID

from sqlalchemy.orm import Session

from models.risk_profile import RiskProfile
from models.user import User
from schemas.risk_profile import OnboardingProgress, RiskProfileUpdate
from services.risk_scoring import calculate_risk_category


def get_risk_profile_by_user(db: Session, user_id: UUID) -> RiskProfile | None:
    return db.query(RiskProfile).filter(RiskProfile.user_id == user_id).first()


def upsert_risk_profile(db: Session, user: User, profile_in: RiskProfileUpdate) -> RiskProfile:
    """Create or replace the user's risk profile and clear any saved onboarding draft."""
    category = calculate_risk_category(profile_in.answers)
    profile = get_risk_profile_by_user(db, user_id=user.id)
    if profile:
        profile.answers = profile_in.answers
        profile.category = category
    else:
        profile = RiskProfile(user_id=user.id, category=category, answers=profile_in.answers)
        db.add(profile)
    user.onboarding_progress = None
    db.commit()
    db.refresh(profile)
    return profile


def save_onboarding_progress(db: Session, user: User, progress: OnboardingProgress) -> None:
    user.onboarding_progress = progress.model_dump()
    db.commit()
