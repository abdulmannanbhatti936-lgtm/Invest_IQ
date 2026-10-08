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


def _signed(email: str, token_type: str, secret: str) -> str:
    from datetime import datetime, timezone

    from jose import jwt

    now = datetime.now(timezone.utc)
    claims = {"sub": email, "type": token_type, "iat": now, "exp": now + timedelta(minutes=5)}
    return jwt.encode(claims, secret, algorithm=settings.JWT_ALGORITHM)


def test_access_and_refresh_tokens_are_not_interchangeable(client):
    email = f"swap_{uuid.uuid4()}@example.com"
    password = "password123"
    client.post("/auth/register", json={"email": email, "full_name": "Swap", "password": password})
    pair = client.post("/auth/login", data={"username": email, "password": password}).json()

    def me(token):
        return client.get("/users/me", headers={"Authorization": f"Bearer {token}"}).status_code

    def refresh(token):
        return client.post("/auth/refresh", json={"refresh_token": token}).status_code

    # Genuine tokens only work in their own role
    assert me(pair["access_token"]) == 200
    assert refresh(pair["refresh_token"]) == 200
    assert me(pair["refresh_token"]) == 401
    assert refresh(pair["access_token"]) == 401

    # The type claim is enforced independently of the signing secret:
    # right secret + wrong type is rejected...
    assert me(_signed(email, "refresh", settings.JWT_SECRET)) == 401
    assert refresh(_signed(email, "access", settings.JWT_REFRESH_SECRET)) == 401
    # ...and right type + wrong secret is rejected too
    assert me(_signed(email, "access", settings.JWT_REFRESH_SECRET)) == 401
    assert refresh(_signed(email, "refresh", settings.JWT_SECRET)) == 401
    # Sanity check: the helper produces tokens the API does accept when both match
    assert me(_signed(email, "access", settings.JWT_SECRET)) == 200
    assert refresh(_signed(email, "refresh", settings.JWT_REFRESH_SECRET)) == 200


def test_passwords_and_tokens_never_logged(client, caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    email = f"logs_{uuid.uuid4()}@example.com"
    password = "Sup3r-Secret-Pa55word"
    client.post("/auth/register", json={"email": email, "full_name": "Logs", "password": password})
    client.post("/auth/login", data={"username": email, "password": "Wrong-Pa55word-xyz"})
    pair = client.post("/auth/login", data={"username": email, "password": password}).json()
    client.get("/users/me", headers={"Authorization": f"Bearer {pair['access_token']}"})
    refreshed = client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]}).json()

    logged = caplog.text
    for secret in [
        password,
        "Wrong-Pa55word-xyz",
        pair["access_token"],
        pair["refresh_token"],
        refreshed["access_token"],
        refreshed["refresh_token"],
    ]:
        assert secret not in logged


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


def test_password_limited_to_72_bytes(client):
    def register(password):
        return client.post(
            "/auth/register",
            json={"email": f"{uuid.uuid4()}@example.com", "full_name": "X", "password": password},
        )

    assert register("a" * 72).status_code == 201
    too_long = register("a" * 73)
    assert too_long.status_code == 422
    assert "72 bytes" in too_long.text
    # Urdu letters take 2 bytes each in UTF-8: 36 fit, 37 do not
    assert register("ب" * 36).status_code == 201
    assert register("ب" * 37).status_code == 422


def test_auth_rate_limit(client, fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT", 3)
    data = {"username": "nobody@example.com", "password": "wrong-password"}
    codes = [client.post("/auth/login", data=data).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401]
    assert codes[3:] == [429, 429]


def test_register_rate_limited(client, fake_redis, monkeypatch):  # Rules.md §6
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT", 2)
    codes = [
        client.post(
            "/auth/register",
            json={
                "email": f"{uuid.uuid4()}@example.com",
                "full_name": "X",
                "password": "password123",
            },
        ).status_code
        for _ in range(4)
    ]
    assert codes == [201, 201, 429, 429]


def test_rate_limit_fails_open_without_redis(client, monkeypatch, caplog):
    import logging

    def broken():
        raise ConnectionError("redis down")

    monkeypatch.setattr("core.rate_limit.get_redis_client", broken)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT", 1)
    caplog.set_level(logging.WARNING, logger="core.rate_limit")
    data = {"username": "nobody@example.com", "password": "wrong-password"}
    assert [client.post("/auth/login", data=data).status_code for _ in range(3)] == [401] * 3
    # Every skipped check is visible as a WARNING (Memory.md §11)
    skips = [
        r for r in caplog.records if r.levelname == "WARNING" and "rate limit SKIPPED" in r.message
    ]
    assert len(skips) == 3
