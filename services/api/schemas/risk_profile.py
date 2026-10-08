from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from models.risk_profile import RiskCategory
from schemas.types import UTCDateTime
from services.risk_scoring import QUESTION_IDS, assess_risk, validate_answers


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
    updated_at: UTCDateTime

    model_config = ConfigDict(from_attributes=True)

    # Derived from the stored answers so the result screen can explain the category
    @computed_field
    @property
    def score(self) -> int:
        return assess_risk(self.answers).score

    @computed_field
    @property
    def caps_applied(self) -> list[str]:
        return assess_risk(self.answers).caps_applied


class OnboardingProgress(BaseModel):
    """Partially-completed questionnaire, saved so onboarding can resume (FR6)."""

    answers: dict[str, str] = Field(default_factory=dict)
    # Index of the question to resume at; the bound follows the questionnaire's length
    current_step: int = Field(default=0, ge=0, le=len(QUESTION_IDS) - 1)

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
