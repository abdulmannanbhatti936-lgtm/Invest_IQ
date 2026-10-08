from models.risk_profile import RiskCategory
from services.risk_scoring import (
    MAX_SCORE,
    MIN_SCORE,
    QUESTION_IDS,
    calculate_risk_category,
    calculate_risk_score,
    validate_answers,
)

AGGRESSIVE = {
    "age_band": "under_30",
    "income_stability": "very_stable",
    "investment_horizon": "long",
    "loss_tolerance": "buy_more",
    "market_experience": "some",
    "investment_goal": "growth",
    "emergency_savings": "over_6_months",
}  # 3+3+3+3+2+3+3 = 20

MODERATE = {
    "age_band": "30_to_50",
    "income_stability": "somewhat_stable",
    "investment_horizon": "medium",
    "loss_tolerance": "hold",
    "market_experience": "some",
    "investment_goal": "income",
    "emergency_savings": "3_to_6_months",
}  # 14

CONSERVATIVE = {
    "age_band": "over_50",
    "income_stability": "unstable",
    "investment_horizon": "short",
    "loss_tolerance": "sell",
    "market_experience": "none",
    "investment_goal": "preservation",
    "emergency_savings": "under_3_months",
}  # 7


def test_questionnaire_has_5_to_10_questions():  # PRD.md FR2
    assert 5 <= len(QUESTION_IDS) <= 10
    assert (MIN_SCORE, MAX_SCORE) == (7, 21)


def test_risk_scoring_categories():
    assert calculate_risk_score(AGGRESSIVE) == 20
    assert calculate_risk_category(AGGRESSIVE) == RiskCategory.aggressive
    assert calculate_risk_score(MODERATE) == 14
    assert calculate_risk_category(MODERATE) == RiskCategory.moderate
    assert calculate_risk_score(CONSERVATIVE) == 7
    assert calculate_risk_category(CONSERVATIVE) == RiskCategory.conservative


def test_risk_scoring_boundaries():
    # 17 is the lowest aggressive score, 16 the highest moderate, 11 the highest conservative
    sixteen = {**MODERATE, "age_band": "under_30", "loss_tolerance": "buy_more"}
    assert calculate_risk_score(sixteen) == 16
    assert calculate_risk_category(sixteen) == RiskCategory.moderate
    seventeen = {**sixteen, "investment_horizon": "long"}
    assert calculate_risk_category(seventeen) == RiskCategory.aggressive
    eleven = {**CONSERVATIVE, "age_band": "under_30", "investment_goal": "growth"}
    assert calculate_risk_score(eleven) == 11
    assert calculate_risk_category(eleven) == RiskCategory.conservative


def test_scoring_tolerates_bad_input():
    assert calculate_risk_score({"age_band": None, "loss_tolerance": 5}) == 0
    assert calculate_risk_category({}) == RiskCategory.conservative


def test_validate_answers():
    assert validate_answers(AGGRESSIVE) == []
    assert validate_answers({"age_band": "under_30"}, partial=True) == []
    assert any("Missing" in e for e in validate_answers({"age_band": "under_30"}))
    assert any("Unknown" in e for e in validate_answers({"shoe_size": "9"}, partial=True))
    assert any("Invalid" in e for e in validate_answers({"age_band": "teen"}, partial=True))


def test_questionnaire_endpoint(client):
    response = client.get("/users/risk-questionnaire")
    assert response.status_code == 200
    assert [q["id"] for q in response.json()] == QUESTION_IDS


def test_read_risk_profile_not_found(client, auth_headers):
    assert client.get("/users/me/risk-profile", headers=auth_headers).status_code == 404


def test_create_read_and_update_risk_profile(client, auth_headers):
    response = client.patch(
        "/users/me/risk-profile", headers=auth_headers, json={"answers": AGGRESSIVE}
    )
    assert response.status_code == 200
    assert response.json()["category"] == "aggressive"

    response = client.get("/users/me/risk-profile", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["category"] == "aggressive"
    assert client.get("/users/me", headers=auth_headers).json()["has_risk_profile"] is True

    # FR5: retake at any time
    response = client.patch(
        "/users/me/risk-profile", headers=auth_headers, json={"answers": CONSERVATIVE}
    )
    assert response.status_code == 200
    assert response.json()["category"] == "conservative"


def test_incomplete_risk_profile_rejected(client, auth_headers):
    response = client.patch(
        "/users/me/risk-profile", headers=auth_headers, json={"answers": {"age_band": "under_30"}}
    )
    assert response.status_code == 422


def test_onboarding_progress_resume_and_clear(client, auth_headers):  # PRD.md FR6
    assert client.get("/users/me/onboarding-progress", headers=auth_headers).json() is None

    draft = {"answers": {"age_band": "under_30", "income_stability": "unstable"}, "current_step": 2}
    response = client.put("/users/me/onboarding-progress", headers=auth_headers, json=draft)
    assert response.status_code == 200
    assert client.get("/users/me/onboarding-progress", headers=auth_headers).json() == draft

    bad = {"answers": {"age_band": "teen"}, "current_step": 1}
    assert (
        client.put("/users/me/onboarding-progress", headers=auth_headers, json=bad).status_code
        == 422
    )

    client.patch("/users/me/risk-profile", headers=auth_headers, json={"answers": MODERATE})
    assert client.get("/users/me/onboarding-progress", headers=auth_headers).json() is None
