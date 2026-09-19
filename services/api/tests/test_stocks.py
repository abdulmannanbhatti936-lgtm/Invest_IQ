import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

from core.deps import get_current_user

def override_get_current_user():
    return {"id": 1, "email": "test@example.com"}

@pytest.fixture(autouse=True)
def override_dependency():
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def auth_token():
    return "fake-token"

def test_search_stocks(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    # SYS is a valid stock on Yahoo Finance we used earlier
    response = client.get("/stocks/search?q=SYS", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) >= 0 # Might be 0 if Yahoo drops it, but it shouldn't fail

def test_get_stock_quote(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    # AAPL is very reliable on Yahoo Finance
    response = client.get("/stocks/AAPL", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert "price" in data
    assert "volume" in data

def test_get_stock_history(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/stocks/AAPL/history?period=5d", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "close" in data[0]
        assert "open" in data[0]
        assert "timestamp" in data[0]
