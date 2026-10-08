from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.risk_profile import RiskCategory
from services.risk_scoring import validate_answers


class RiskProfileUpdate(BaseModel):
    answers: dict[str, str]

    @field_validator("answers")
    @classmethod
    def answers_complete_and_valid(cls, v: dict[str, str]) -> dict[str, str]:
        errors = validate_answers(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v


RiskProfileCreate = RiskProfileUpdate


class RiskProfile(BaseModel):
    id: UUID
    user_id: UUID
    category: RiskCategory
    answers: dict
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OnboardingProgress(BaseModel):
    """Partially-completed questionnaire, saved so onboarding can resume (FR6)."""

    answers: dict[str, str] = Field(default_factory=dict)
    current_step: int = Field(default=0, ge=0)

    @field_validator("answers")
    @classmethod
    def answers_valid(cls, v: dict[str, str]) -> dict[str, str]:
        errors = validate_answers(v, partial=True)
        if errors:
            raise ValueError("; ".join(errors))
        return v


class QuestionnaireQuestion(BaseModel):
    id: str
    options: list[str]
