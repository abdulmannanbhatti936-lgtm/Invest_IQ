"""
Risk questionnaire definition and scoring (PRD.md FR2/FR3).

Pure functions only, so classification is unit-testable without a database
(Rules.md §3.2). The web and mobile apps render the same question ids and
option values; the human-readable text lives in packages/i18n.
"""

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


def calculate_risk_category(answers: dict) -> RiskCategory:
    """
    Classify a completed questionnaire.
    7-11 -> conservative, 12-16 -> moderate, 17-21 -> aggressive.
    """
    score = calculate_risk_score(answers)
    if score >= AGGRESSIVE_MIN_SCORE:
        return RiskCategory.aggressive
    if score >= MODERATE_MIN_SCORE:
        return RiskCategory.moderate
    return RiskCategory.conservative
