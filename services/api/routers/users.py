import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from crud.risk_profile import (
    get_risk_profile_by_user,
    save_onboarding_progress,
    upsert_risk_profile,
)
from models.user import User
from schemas.risk_profile import (
    OnboardingProgress,
    QuestionnaireQuestion,
    RiskProfileUpdate,
)
from schemas.risk_profile import RiskProfile as RiskProfileSchema
from schemas.user import User as UserSchema
from services.risk_scoring import QUESTIONNAIRE

router = APIRouter(prefix="/users", tags=["users"])


class _DuplicateKeys(Exception):
    def __init__(self, keys: list[str]):
        self.keys = keys


def _no_duplicates(pairs: list[tuple]) -> dict:
    keys = [k for k, _ in pairs]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    if dupes:
        raise _DuplicateKeys(dupes)
    return dict(pairs)


async def reject_duplicate_answers(request: Request) -> None:
    """
    A JSON object with a repeated key (e.g. two "age_band" answers) is silently
    collapsed to the last value by normal parsing; reject it with a 422 instead.
    """
    try:
        json.loads(await request.body() or b"null", object_pairs_hook=_no_duplicates)
    except _DuplicateKeys as e:
        raise RequestValidationError(
            [
                {
                    "type": "duplicate_key",
                    "loc": ("body",),
                    "msg": f"Duplicate answer for: {', '.join(e.keys)}",
                    "input": None,
                }
            ]
        ) from None
    except ValueError:
        return  # malformed JSON: FastAPI's own body parsing returns the 422


@router.get("/me", response_model=UserSchema)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/risk-questionnaire", response_model=list[QuestionnaireQuestion])
def read_risk_questionnaire():
    """Question ids and option values; display text lives in packages/i18n."""
    return [{"id": q, "options": list(opts)} for q, opts in QUESTIONNAIRE.items()]


@router.get("/me/risk-profile", response_model=RiskProfileSchema)
def read_risk_profile(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    profile = get_risk_profile_by_user(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Risk profile not found")
    return profile


@router.patch(
    "/me/risk-profile",
    response_model=RiskProfileSchema,
    dependencies=[Depends(reject_duplicate_answers)],
)
def update_or_create_risk_profile(
    profile_in: RiskProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return upsert_risk_profile(db, user=current_user, profile_in=profile_in)


@router.get("/me/onboarding-progress", response_model=OnboardingProgress | None)
def read_onboarding_progress(current_user: User = Depends(get_current_user)):
    return current_user.onboarding_progress


@router.put(
    "/me/onboarding-progress",
    response_model=OnboardingProgress,
    dependencies=[Depends(reject_duplicate_answers)],
)
def update_onboarding_progress(
    progress: OnboardingProgress,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    save_onboarding_progress(db, user=current_user, progress=progress)
    return progress
