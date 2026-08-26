import uuid

from fastapi.testclient import TestClient

from main import app

# Use a test database or just create tables in the existing one
# For this test, we'll use the main database but clean up

client = TestClient(app)

def test_register_and_login():
    test_email = f"test_{uuid.uuid4()}@example.com"
    test_password = "password123"
    
    # Register
    response = client.post(
        "/auth/register",
        json={
            "email": test_email,
            "full_name": "Test User",
            "password": test_password
        }
    )
    assert response.status_code == 201
    
    # Login
    login_response = client.post(
        "/auth/login",
        data={
            "username": test_email,
            "password": test_password
        }
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    # Test protected route
    me_response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == test_email
