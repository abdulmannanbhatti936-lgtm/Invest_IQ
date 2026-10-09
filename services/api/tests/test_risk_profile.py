import json
import uuid

import pytest

from models.risk_profile import RiskCategory
from services.risk_scoring import (
    MAX_SCORE,
    MIN_SCORE,
    QUESTION_IDS,
    assess_risk,
    calculate_risk_category,
    calculate_risk_score,
    validate_answers,
)
from tests.conftest import register_and_login

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


MAXIMUM = {**AGGRESSIVE, "market_experience": "experienced"}  # 21, every top answer


def test_assess_uncapped_categories():
    for answers, score, category in [
        (MAXIMUM, 21, RiskCategory.aggressive),
        (MODERATE, 14, RiskCategory.moderate),
        (CONSERVATIVE, 7, RiskCategory.conservative),
    ]:
        result = assess_risk(answers)
        assert (result.score, result.score_category, result.category) == (score, category, category)
        assert result.caps_applied == []  # CONSERVATIVE trips every cap but none lowers it


def test_short_horizon_caps_aggressive_scorer_at_conservative():
    result = assess_risk({**MAXIMUM, "investment_horizon": "short"})
    assert result.score == 19
    assert result.score_category == RiskCategory.aggressive
    assert result.category == RiskCategory.conservative
    assert result.caps_applied == ["short_horizon"]


def test_short_horizon_caps_moderate_scorer_at_conservative():
    result = assess_risk({**MODERATE, "investment_horizon": "short"})
    assert (result.score, result.score_category) == (13, RiskCategory.moderate)
    assert result.category == RiskCategory.conservative
    assert result.caps_applied == ["short_horizon"]


def test_sell_on_loss_caps_aggressive_scorer_at_moderate():
    result = assess_risk({**MAXIMUM, "loss_tolerance": "sell"})
    assert (result.score, result.score_category) == (19, RiskCategory.aggressive)
    assert result.category == RiskCategory.moderate
    assert result.caps_applied == ["sells_on_loss"]


def test_low_emergency_savings_caps_aggressive_scorer_at_moderate():
    result = assess_risk({**MAXIMUM, "emergency_savings": "under_3_months"})
    assert (result.score, result.score_category) == (19, RiskCategory.aggressive)
    assert result.category == RiskCategory.moderate
    assert result.caps_applied == ["low_emergency_savings"]


def test_both_moderate_caps_listed_together():
    result = assess_risk(
        {**MAXIMUM, "loss_tolerance": "sell", "emergency_savings": "under_3_months"}
    )
    assert (result.score, result.score_category) == (17, RiskCategory.aggressive)
    assert result.category == RiskCategory.moderate
    assert result.caps_applied == ["sells_on_loss", "low_emergency_savings"]


def test_conservative_cap_wins_over_moderate_cap():
    result = assess_risk({**MAXIMUM, "investment_horizon": "short", "loss_tolerance": "sell"})
    assert (result.score, result.score_category) == (17, RiskCategory.aggressive)
    assert result.category == RiskCategory.conservative
    assert result.caps_applied == ["short_horizon", "sells_on_loss"]


def test_moderate_cap_never_raises_or_changes_a_lower_category():
    moderate = {**MODERATE, "loss_tolerance": "sell"}  # 13 -> moderate already
    result = assess_risk(moderate)
    assert result.category == RiskCategory.moderate
    assert result.caps_applied == []
    assert calculate_risk_category(moderate) == RiskCategory.moderate


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
    # Public endpoint: only ids and option values. Points and thresholds stay server-side.
    for question in response.json():
        assert set(question) == {"id", "options"}
        assert all(isinstance(option, str) for option in question["options"])


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


def test_capped_profile_explains_cap_via_api(client, auth_headers):
    response = client.patch(
        "/users/me/risk-profile",
        headers=auth_headers,
        json={"answers": {**MAXIMUM, "investment_horizon": "short"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "conservative"
    assert body["score"] == 19
    assert body["caps_applied"] == ["short_horizon"]

    body = client.get("/users/me/risk-profile", headers=auth_headers).json()
    assert body["caps_applied"] == ["short_horizon"]


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


# ---- Step 1.3 audit


def test_scoring_uses_the_approved_values():  # Memory.md §3, 2026-10-09
    from services.risk_scoring import AGGRESSIVE_MIN_SCORE, MODERATE_MIN_SCORE, QUESTIONNAIRE

    assert len(QUESTIONNAIRE) == 7
    for options in QUESTIONNAIRE.values():
        assert sorted(options.values(), reverse=True) == [3, 2, 1]
    assert (MODERATE_MIN_SCORE, AGGRESSIVE_MIN_SCORE) == (12, 17)
    twelve = {**MODERATE, "age_band": "over_50", "income_stability": "unstable"}  # 14 - 2
    assert calculate_risk_score(twelve) == 12
    assert assess_risk(twelve).category == RiskCategory.moderate


def test_scoring_module_is_pure():  # Rules.md §3.2: no DB/HTTP inside the scoring logic
    import ast
    import inspect

    import services.risk_scoring as scoring

    tree = ast.parse(inspect.getsource(scoring))
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imported == {"dataclasses", "models.risk_profile"}  # the enum only


@pytest.mark.parametrize(
    "body",
    [
        {"answers": {**AGGRESSIVE, "shoe_size": "9"}},  # unknown question id
        {"answers": {**AGGRESSIVE, "age_band": "teen"}},  # unknown option
        {"answers": {k: v for k, v in AGGRESSIVE.items() if k != "age_band"}},  # missing
        {"answers": {**AGGRESSIVE, "age_band": 3}},  # not a string
        {"answers": {**AGGRESSIVE, "age_band": ["under_30", "over_50"]}},  # two answers
        {"answers": None},
        {},
    ],
)
def test_invalid_answers_rejected_with_422(client, auth_headers, body):
    response = client.patch("/users/me/risk-profile", headers=auth_headers, json=body)
    assert response.status_code == 422


def test_duplicate_answers_rejected_with_422(client, auth_headers):
    headers = {**auth_headers, "Content-Type": "application/json"}
    full = json.dumps({"answers": AGGRESSIVE})
    duplicated = full[:-2] + ', "age_band": "over_50"}}'  # age_band appears twice
    response = client.patch("/users/me/risk-profile", headers=headers, content=duplicated)
    assert response.status_code == 422
    assert "Duplicate answer for: age_band" in response.text

    draft = '{"answers": {"age_band": "under_30", "age_band": "over_50"}, "current_step": 1}'
    assert (
        client.put("/users/me/onboarding-progress", headers=headers, content=draft).status_code
        == 422
    )
    # Nothing was saved by either rejected request
    assert client.get("/users/me/risk-profile", headers=auth_headers).status_code == 404
    assert client.get("/users/me/onboarding-progress", headers=auth_headers).json() is None


def test_draft_step_must_be_a_real_question(client, auth_headers):
    for step, expected in [(0, 200), (len(QUESTION_IDS) - 1, 200), (len(QUESTION_IDS), 422)]:
        response = client.put(
            "/users/me/onboarding-progress",
            headers=auth_headers,
            json={"answers": {}, "current_step": step},
        )
        assert response.status_code == expected


def test_retake_replaces_profile_and_bumps_updated_at(client, auth_headers, db):  # FR5
    from models.risk_profile import RiskProfile

    first = client.patch(
        "/users/me/risk-profile", headers=auth_headers, json={"answers": AGGRESSIVE}
    ).json()
    same_again = client.patch(
        "/users/me/risk-profile", headers=auth_headers, json={"answers": AGGRESSIVE}
    ).json()
    assert same_again["id"] == first["id"]
    assert same_again["updated_at"] > first["updated_at"]  # even with identical answers

    retaken = client.patch(
        "/users/me/risk-profile", headers=auth_headers, json={"answers": CONSERVATIVE}
    ).json()
    assert retaken["id"] == first["id"]
    assert retaken["category"] == "conservative"
    assert retaken["answers"] == CONSERVATIVE
    assert retaken["updated_at"] > same_again["updated_at"]
    assert db.query(RiskProfile).filter(RiskProfile.user_id == first["user_id"]).count() == 1


def test_onboarding_save_resume_complete(client):  # FR6
    email = f"resume_{uuid.uuid4()}@example.com"
    client.post(
        "/auth/register", json={"email": email, "full_name": "Re", "password": "password123"}
    )

    def login():
        token = client.post(
            "/auth/login", data={"username": email, "password": "password123"}
        ).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    # Session 1: answer two questions, then abandon
    session1 = login()
    first_two = dict(list(AGGRESSIVE.items())[:2])
    client.put(
        "/users/me/onboarding-progress",
        headers=session1,
        json={"answers": first_two, "current_step": 2},
    )

    # Session 2 (fresh login): the draft is still there and onboarding is not done
    session2 = login()
    assert client.get("/users/me", headers=session2).json()["has_risk_profile"] is False
    resumed = client.get("/users/me/onboarding-progress", headers=session2).json()
    assert resumed == {"answers": first_two, "current_step": 2}

    # Continue from the saved step, then finish
    six = dict(list(AGGRESSIVE.items())[:6])
    client.put(
        "/users/me/onboarding-progress", headers=session2, json={"answers": six, "current_step": 6}
    )
    assert client.get("/users/me/onboarding-progress", headers=session2).json()["current_step"] == 6
    done = client.patch("/users/me/risk-profile", headers=session2, json={"answers": AGGRESSIVE})
    assert done.status_code == 200

    # Completing clears the draft and marks onboarding done
    assert client.get("/users/me/onboarding-progress", headers=session2).json() is None
    assert client.get("/users/me", headers=session2).json()["has_risk_profile"] is True


def test_users_cannot_access_each_others_data(client):
    user_a = register_and_login(client)
    user_b = register_and_login(client)

    client.patch("/users/me/risk-profile", headers=user_a, json={"answers": AGGRESSIVE})
    a_draft = {"answers": {"age_band": "under_30"}, "current_step": 1}
    client.put("/users/me/onboarding-progress", headers=user_a, json=a_draft)

    # B sees only B's (empty) data
    assert client.get("/users/me/risk-profile", headers=user_b).status_code == 404
    assert client.get("/users/me/onboarding-progress", headers=user_b).json() is None

    # B's writes never touch A's data
    client.patch("/users/me/risk-profile", headers=user_b, json={"answers": CONSERVATIVE})
    client.put(
        "/users/me/onboarding-progress",
        headers=user_b,
        json={"answers": {"age_band": "over_50"}, "current_step": 1},
    )
    a_profile = client.get("/users/me/risk-profile", headers=user_a).json()
    b_profile = client.get("/users/me/risk-profile", headers=user_b).json()
    assert a_profile["category"] == "aggressive"
    assert b_profile["category"] == "conservative"
    assert a_profile["user_id"] != b_profile["user_id"]
    assert client.get("/users/me/onboarding-progress", headers=user_a).json() == a_draft

    # There is no way to address another user's profile: no user-id routes exist
    assert client.get(
        f"/users/{a_profile['user_id']}/risk-profile", headers=user_b
    ).status_code in (
        404,
        405,
    )


def test_deleting_user_via_orm_removes_their_profile(db):
    # passive_deletes=True leaves the child rows to the DB's ON DELETE CASCADE; without it the
    # ORM would try to set risk_profiles.user_id to NULL and fail the NOT NULL constraint.
    from models.risk_profile import RiskProfile
    from models.user import User

    email = f"cascade_{uuid.uuid4().hex[:8]}@example.com"
    user = User(email=email, password_hash="x", full_name="C")
    db.add(user)
    db.flush()
    db.add(RiskProfile(user_id=user.id, category=RiskCategory.moderate, answers={}))
    db.commit()
    user_id = user.id
    db.expire_all()

    db.delete(db.get(User, user_id))
    db.commit()

    assert db.query(RiskProfile).filter(RiskProfile.user_id == user_id).count() == 0
