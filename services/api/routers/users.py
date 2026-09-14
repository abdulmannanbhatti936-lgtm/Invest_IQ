from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from models.user import User
from schemas.user import User as UserSchema
from schemas.risk_profile import RiskProfile as RiskProfileSchema, RiskProfileCreate, RiskProfileUpdate
from core.deps import get_current_user
from core.database import get_db
from crud.risk_profile import get_risk_profile_by_user, create_risk_profile, update_risk_profile

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserSchema)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/me/risk-profile", response_model=RiskProfileSchema)
def read_risk_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = get_risk_profile_by_user(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Risk profile not found")
    return profile

@router.patch("/me/risk-profile", response_model=RiskProfileSchema)
def update_or_create_risk_profile(
    profile_in: RiskProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = get_risk_profile_by_user(db, user_id=current_user.id)
    if profile:
        profile = update_risk_profile(db, db_profile=profile, profile_in=profile_in)
    else:
        # Create if it doesn't exist
        profile = create_risk_profile(db, user_id=current_user.id, profile_in=RiskProfileCreate(answers=profile_in.answers))
    return profile
