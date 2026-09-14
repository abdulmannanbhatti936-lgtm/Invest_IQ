import pytest
from services.risk_scoring import calculate_risk_category
from models.risk_profile import RiskCategory

def test_risk_scoring_aggressive():
    answers = {
        "age": 25,
        "investment_goal": "growth",
        "risk_tolerance": "high",
        "time_horizon": "long"
    }
    # 25 (<30) -> 3
    # growth -> 3
    # high -> 3
    # long -> 3
    # Total = 12 (>= 10 -> aggressive)
    category = calculate_risk_category(answers)
    assert category == RiskCategory.aggressive

def test_risk_scoring_moderate():
    answers = {
        "age": 40,
        "investment_goal": "income",
        "risk_tolerance": "medium",
        "time_horizon": "medium"
    }
    # 40 (<50) -> 2
    # income -> 2
    # medium -> 2
    # medium -> 2
    # Total = 8 (>= 7 and < 10 -> moderate)
    category = calculate_risk_category(answers)
    assert category == RiskCategory.moderate

def test_risk_scoring_conservative():
    answers = {
        "age": 60,
        "investment_goal": "preservation",
        "risk_tolerance": "low",
        "time_horizon": "short"
    }
    # 60 (>=50) -> 1
    # preservation -> 1
    # low -> 1
    # short -> 1
    # Total = 4 (< 7 -> conservative)
    category = calculate_risk_category(answers)
    assert category == RiskCategory.conservative

def test_risk_scoring_missing_fields_defaults_to_conservative():
    answers = {}
    # default age 35 -> 2
    # no goal -> 0
    # no tolerance -> 0
    # no horizon -> 0
    # Total = 2 (< 7 -> conservative)
    category = calculate_risk_category(answers)
    assert category == RiskCategory.conservative

import uuid
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

@pytest.fixture
def user_token_headers():
    test_email = f"test_{uuid.uuid4()}@example.com"
    test_password = "password123"
    
    # Register
    client.post(
        "/auth/register",
        json={
            "email": test_email,
            "full_name": "Test User",
            "password": test_password
        }
    )
    
    # Login
    login_response = client.post(
        "/auth/login",
        data={
            "username": test_email,
            "password": test_password
        }
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_read_risk_profile_not_found(user_token_headers):
    response = client.get("/users/me/risk-profile", headers=user_token_headers)
    assert response.status_code == 404

def test_create_and_read_risk_profile(user_token_headers):
    data = {
        "answers": {
            "age": 28,
            "investment_goal": "growth",
            "risk_tolerance": "high",
            "time_horizon": "long"
        }
    }
    response = client.patch("/users/me/risk-profile", headers=user_token_headers, json=data)
    assert response.status_code == 200
    content = response.json()
    assert content["category"] == "aggressive"
    assert "answers" in content
    
    # Now read it
    response = client.get("/users/me/risk-profile", headers=user_token_headers)
    assert response.status_code == 200
    content = response.json()
    assert content["category"] == "aggressive"

def test_update_risk_profile(user_token_headers):
    # First create
    client.patch("/users/me/risk-profile", headers=user_token_headers, json={
        "answers": {"age": 28, "investment_goal": "growth", "risk_tolerance": "high", "time_horizon": "long"}
    })
    
    # Now update to conservative
    data = {
        "answers": {
            "age": 65,
            "investment_goal": "preservation",
            "risk_tolerance": "low",
            "time_horizon": "short"
        }
    }
    response = client.patch("/users/me/risk-profile", headers=user_token_headers, json=data)
    assert response.status_code == 200
    content = response.json()
    assert content["category"] == "conservative"
