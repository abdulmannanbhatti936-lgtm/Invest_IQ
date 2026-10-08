"""
Risk questionnaire definition and scoring (PRD.md FR2/FR3).

Pure functions only, so classification is unit-testable without a database
(Rules.md §3.2). The web and mobile apps render the same question ids and
option values; the human-readable text lives in packages/i18n.
"""

from dataclasses import dataclass, field

from models.risk_profile import RiskCategory

# question id -> {option value: points}. Higher points = higher risk capacity.
QUESTIONNAIRE: dict[str, dict[str, int]] = {
    "age_band": {"under_30": 3, "30_to_50": 2, "over_50": 1},
    "income_stability": {"very_stable": 3, "somewhat_stable": 2, "unstable": 1},
    "investment_horizon": {"long": 3, "medium": 2, "short": 1},
    "loss_tolerance": {"buy_more": 3, "hold": 2, "sell": 1},
    "market_experience": {"experienced": 3, "some": 2, "none": 1},
    "investment_goal": {"growth": 3, "income": 2, "preservation": 1},
    "emergency_savings": {"over_6_months": 3, "3_to_6_months": 2, "under_3_months": 1},
}

QUESTION_IDS = list(QUESTIONNAIRE.keys())

MIN_SCORE = len(QUESTIONNAIRE)  # 7
MAX_SCORE = 3 * len(QUESTIONNAIRE)  # 21
AGGRESSIVE_MIN_SCORE = 17
MODERATE_MIN_SCORE = 12


def validate_answers(answers: dict, *, partial: bool = False) -> list[str]:
    """
    Return a list of human-readable problems with the answers (empty = valid).
    With partial=True, missing questions are allowed (saved onboarding progress).
    """
    errors: list[str] = []
    for key, value in answers.items():
        if key not in QUESTIONNAIRE:
            errors.append(f"Unknown question '{key}'")
        elif value not in QUESTIONNAIRE[key]:
            allowed = ", ".join(QUESTIONNAIRE[key])
            errors.append(f"Invalid answer '{value}' for '{key}' (allowed: {allowed})")
    if not partial:
        missing = [q for q in QUESTION_IDS if q not in answers]
        if missing:
            errors.append(f"Missing answers for: {', '.join(missing)}")
    return errors


def calculate_risk_score(answers: dict) -> int:
    """Sum of option points. Unknown or missing answers score 0."""
    score = 0
    for question, options in QUESTIONNAIRE.items():
        value = answers.get(question)
        if isinstance(value, str):
            score += options.get(value, 0)
    return score


def category_for_score(score: int) -> RiskCategory:
    """7-11 -> conservative, 12-16 -> moderate, 17-21 -> aggressive."""
    if score >= AGGRESSIVE_MIN_SCORE:
        return RiskCategory.aggressive
    if score >= MODERATE_MIN_SCORE:
        return RiskCategory.moderate
    return RiskCategory.conservative


_CATEGORY_RANK = {
    RiskCategory.conservative: 0,
    RiskCategory.moderate: 1,
    RiskCategory.aggressive: 2,
}

# Safety caps applied after scoring (team decision, 2026-10-09):
# cap id -> (question, triggering answer, highest category allowed).
# Cap ids double as i18n keys for the plain-language explanation.
SAFETY_CAPS: dict[str, tuple[str, str, RiskCategory]] = {
    "short_horizon": ("investment_horizon", "short", RiskCategory.conservative),
    "sells_on_loss": ("loss_tolerance", "sell", RiskCategory.moderate),
    "low_emergency_savings": ("emergency_savings", "under_3_months", RiskCategory.moderate),
}


@dataclass(frozen=True)
class RiskAssessment:
    score: int
    score_category: RiskCategory  # what the score alone gives
    category: RiskCategory  # final category after safety caps
    caps_applied: list[str] = field(default_factory=list)  # caps that lowered the category


def assess_risk(answers: dict) -> RiskAssessment:
    """
    Score a completed questionnaire, then apply the safety caps.
    A cap counts as applied only if it actually lowered the score-based category.
    """
    score = calculate_risk_score(answers)
    score_category = category_for_score(score)
    category = score_category
    caps_applied: list[str] = []
    for cap_id, (question, trigger, ceiling) in SAFETY_CAPS.items():
        if answers.get(question) != trigger:
            continue
        if _CATEGORY_RANK[ceiling] < _CATEGORY_RANK[score_category]:
            caps_applied.append(cap_id)
        if _CATEGORY_RANK[ceiling] < _CATEGORY_RANK[category]:
            category = ceiling
    return RiskAssessment(score, score_category, category, caps_applied)


def calculate_risk_category(answers: dict) -> RiskCategory:
    """Final category (score thresholds + safety caps)."""
    return assess_risk(answers).category
