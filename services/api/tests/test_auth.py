import uuid

from fastapi.testclient import TestClient

from main import app

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
    
    # Register Duplicate Email
    response_dup = client.post(
        "/auth/register",
        json={
            "email": test_email,
            "full_name": "Test User 2",
            "password": "password456"
        }
    )
    assert response_dup.status_code == 400
    assert "already exists" in response_dup.json()["detail"]
    
    # Login
    login_response = client.post(
        "/auth/login",
        data={
            "username": test_email,
            "password": test_password
        }
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    
    # Login Wrong Password
    login_wrong_pwd = client.post(
        "/auth/login",
        data={
            "username": test_email,
            "password": "wrongpassword"
        }
    )
    assert login_wrong_pwd.status_code == 401
    
    # Login Non-existent user
    login_wrong_user = client.post(
        "/auth/login",
        data={
            "username": "doesnotexist@example.com",
            "password": test_password
        }
    )
    assert login_wrong_user.status_code == 401

    # Test protected route with valid token
    me_response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == test_email
    
    # Test protected route with invalid token
    me_invalid = client.get(
        "/users/me",
        headers={"Authorization": "Bearer invalidtoken123"}
    )
    assert me_invalid.status_code == 401
    
    # Test refresh token
    refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": token_data["refresh_token"]}
    )
    assert refresh_response.status_code == 200
    new_token_data = refresh_response.json()
    assert "access_token" in new_token_data
    assert "refresh_token" in new_token_data
    assert new_token_data["access_token"] != token_data["access_token"]
    
    # Test refresh token with invalid token
    refresh_invalid = client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid_refresh_token"}
    )
    assert refresh_invalid.status_code == 401
    
    # Test refresh endpoint using an access token instead of a refresh token
    refresh_wrong_type = client.post(
        "/auth/refresh",
        json={"refresh_token": token_data["access_token"]}
    )
    assert refresh_wrong_type.status_code == 401
