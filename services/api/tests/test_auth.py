import uuid
from datetime import timedelta

import pytest

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


# ---- Step 1.4 audit: token edge cases and user enumeration


def _new_user(client) -> tuple[str, dict]:
    email = f"edge_{uuid.uuid4()}@example.com"
    client.post(
        "/auth/register", json={"email": email, "full_name": "Edge", "password": "password123"}
    )
    pair = client.post("/auth/login", data={"username": email, "password": "password123"}).json()
    return email, pair


def _me(client, token):
    return client.get("/users/me", headers={"Authorization": f"Bearer {token}"})


def _refresh(client, token):
    return client.post("/auth/refresh", json={"refresh_token": token})


def test_expired_refresh_token_rejected(client):
    email, _ = _new_user(client)
    expired = create_refresh_token(email, expires_delta=timedelta(seconds=-1))
    response = _refresh(client, expired)
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_malformed_and_tampered_tokens_rejected(client):
    import base64
    import json

    from jose import jwt

    email, pair = _new_user(client)
    other_email, _ = _new_user(client)
    header, payload, signature = pair["access_token"].split(".")

    def b64(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
    flipped = signature[:-2] + ("AA" if signature[-2:] != "AA" else "BB")
    forged_access = {
        "garbage": "not-a-jwt",
        "two segments": f"{header}.{payload}",
        "flipped signature": f"{header}.{payload}.{flipped}",
        # payload edited to another user's email, original signature kept
        "swapped subject": f"{header}.{b64({**claims, 'sub': other_email})}.{signature}",
        # 'alg: none' with no signature must never be accepted
        "alg none": f"{b64({'alg': 'none', 'typ': 'JWT'})}.{payload}.",
        "unrelated secret": jwt.encode(claims, "attacker-secret", algorithm="HS256"),
    }
    for name, token in forged_access.items():
        assert _me(client, token).status_code == 401, name
        assert _refresh(client, token).status_code == 401, name

    r_header, r_payload, r_sig = pair["refresh_token"].split(".")
    r_claims = json.loads(base64.urlsafe_b64decode(r_payload + "=="))
    tampered_refresh = f"{r_header}.{b64({**r_claims, 'sub': other_email})}.{r_sig}"
    assert _refresh(client, tampered_refresh).status_code == 401

    # The genuine tokens still work, so the 401s above come from the tampering
    assert _me(client, pair["access_token"]).status_code == 200
    assert _refresh(client, pair["refresh_token"]).status_code == 200


def test_tokens_for_deleted_user_rejected(client, db):
    from models.user import User

    email, pair = _new_user(client)
    assert _me(client, pair["access_token"]).status_code == 200

    db.query(User).filter(User.email == email).delete()
    db.commit()

    assert _me(client, pair["access_token"]).status_code == 401
    assert _refresh(client, pair["refresh_token"]).status_code == 401


def test_login_does_not_reveal_whether_email_exists(client):
    email, _ = _new_user(client)
    wrong_password = client.post("/auth/login", data={"username": email, "password": "Wrong-pass1"})
    unknown_email = client.post(
        "/auth/login",
        data={"username": f"nobody_{uuid.uuid4()}@example.com", "password": "Wrong-pass1"},
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert (
        wrong_password.json() == unknown_email.json() == {"detail": "Incorrect email or password"}
    )
    assert (
        wrong_password.headers["www-authenticate"]
        == unknown_email.headers["www-authenticate"]
        == "Bearer"
    )


def test_unknown_email_still_runs_one_password_check(client, monkeypatch):
    # Deterministic stand-in for a timing test: an unknown email must cost the same bcrypt
    # check as a wrong password, so response time can't reveal registered emails.
    import routers.auth as auth_router

    calls = []
    real_verify = auth_router.verify_password

    def spy(plain, hashed):
        calls.append(hashed)
        return real_verify(plain, hashed)

    monkeypatch.setattr(auth_router, "verify_password", spy)

    unknown = client.post(
        "/auth/login",
        data={"username": f"nobody_{uuid.uuid4()}@example.com", "password": "Wrong-pass1"},
    )
    assert unknown.status_code == 401
    assert calls == [auth_router._DUMMY_PASSWORD_HASH]

    email, _ = _new_user(client)
    calls.clear()
    assert (
        client.post("/auth/login", data={"username": email, "password": "Wrong-pass1"}).status_code
        == 401
    )
    assert len(calls) == 1 and calls[0] != auth_router._DUMMY_PASSWORD_HASH

    # Typing the dummy password for an unknown email still fails
    calls.clear()
    assert (
        client.post(
            "/auth/login",
            data={
                "username": f"nobody_{uuid.uuid4()}@example.com",
                "password": "investiq-timing-equaliser-not-a-real-password",
            },
        ).status_code
        == 401
    )


def test_email_is_case_insensitive(client):
    local = f"Mixed.Case_{uuid.uuid4().hex[:8]}"
    typed = f"  {local}@Example.COM "
    stored = f"{local}@example.com".lower()

    response = client.post(
        "/auth/register", json={"email": typed, "full_name": "Case", "password": "password123"}
    )
    assert response.status_code == 201
    assert response.json()["email"] == stored

    # Log in with exactly what was typed at registration, and with other casings
    for username in (typed, stored, stored.upper()):
        login = client.post("/auth/login", data={"username": username, "password": "password123"})
        assert login.status_code == 200, username

    # An address that differs only by letter case is the same account
    duplicate = client.post(
        "/auth/register",
        json={"email": stored.upper(), "full_name": "Case 2", "password": "password456"},
    )
    assert duplicate.status_code == 400


def test_database_rejects_emails_differing_only_by_case(db):
    from sqlalchemy.exc import IntegrityError

    from models.user import User

    email = f"dbcase_{uuid.uuid4().hex[:8]}@example.com"
    db.add(User(email=email, password_hash="x", full_name="A"))
    db.commit()
    # Bypasses the API on purpose: the unique index on lower(email) must still catch it
    db.add(User(email=email.upper(), password_hash="x", full_name="B"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
