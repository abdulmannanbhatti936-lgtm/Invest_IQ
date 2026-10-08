import uuid
from datetime import timedelta

from core.config import settings
from core.security import create_access_token, create_refresh_token


def test_register_and_login(client):
    test_email = f"test_{uuid.uuid4()}@example.com"
    test_password = "password123"

    response = client.post(
        "/auth/register",
        json={"email": test_email, "full_name": "Test User", "password": test_password},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "user"
    assert body["has_risk_profile"] is False
    assert "password_hash" not in body

    response_dup = client.post(
        "/auth/register",
        json={"email": test_email, "full_name": "Test User 2", "password": "password456"},
    )
    assert response_dup.status_code == 400
    assert "already exists" in response_dup.json()["detail"]

    login_response = client.post(
        "/auth/login", data={"username": test_email, "password": test_password}
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data

    assert (
        client.post(
            "/auth/login", data={"username": test_email, "password": "wrongpassword"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login",
            data={"username": "doesnotexist@example.com", "password": test_password},
        ).status_code
        == 401
    )

    me_response = client.get(
        "/users/me", headers={"Authorization": f"Bearer {token_data['access_token']}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == test_email

    # No token / invalid token
    assert client.get("/users/me").status_code == 401
    assert (
        client.get("/users/me", headers={"Authorization": "Bearer invalidtoken123"}).status_code
        == 401
    )

    refresh_response = client.post(
        "/auth/refresh", json={"refresh_token": token_data["refresh_token"]}
    )
    assert refresh_response.status_code == 200
    new_token_data = refresh_response.json()
    assert "access_token" in new_token_data
    assert "refresh_token" in new_token_data

    assert (
        client.post("/auth/refresh", json={"refresh_token": "invalid_refresh_token"}).status_code
        == 401
    )
    # An access token must not work as a refresh token...
    assert (
        client.post("/auth/refresh", json={"refresh_token": token_data["access_token"]}).status_code
        == 401
    )
    # ...and a refresh token must not work as an access token
    assert (
        client.get(
            "/users/me", headers={"Authorization": f"Bearer {token_data['refresh_token']}"}
        ).status_code
        == 401
    )


def test_expired_access_token_rejected(client, auth_headers):
    email = client.get("/users/me", headers=auth_headers).json()["email"]
    expired = create_access_token(email, expires_delta=timedelta(seconds=-1))
    assert (
        client.get("/users/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    )


def test_refresh_token_signed_with_separate_secret():
    from jose import jwt

    token = create_refresh_token("someone@example.com")
    payload = jwt.decode(token, settings.JWT_REFRESH_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert payload["type"] == "refresh"
    try:
        jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except Exception:
        return
    raise AssertionError("refresh token must not verify with the access-token secret")


def test_register_validates_input(client):
    assert (
        client.post(
            "/auth/register",
            json={"email": "not-an-email", "full_name": "X", "password": "password123"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/auth/register",
            json={"email": f"{uuid.uuid4()}@example.com", "full_name": "X", "password": "short"},
        ).status_code
        == 422
    )


def test_auth_rate_limit(client, fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT", 3)
    data = {"username": "nobody@example.com", "password": "wrong-password"}
    codes = [client.post("/auth/login", data=data).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401]
    assert codes[3:] == [429, 429]


def test_rate_limit_fails_open_without_redis(client, monkeypatch):
    def broken():
        raise ConnectionError("redis down")

    monkeypatch.setattr("core.rate_limit.get_redis_client", broken)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT", 1)
    data = {"username": "nobody@example.com", "password": "wrong-password"}
    assert [client.post("/auth/login", data=data).status_code for _ in range(3)] == [401] * 3
