"""
Phase 7: the /notifications endpoints. Login and a risk profile are required; one user's
notifications, settings and devices are never reachable from another account; requests are
rate-limited per user; settings default to everything off.
"""

import datetime
import uuid

import pytest

from core.config import settings
from models.notification import Notification, PushDevice
from models.risk_profile import RiskCategory, RiskProfile
from models.user import User
from tests.conftest import register_and_login


def _user(client, db, headers) -> User:
    email = client.get("/users/me", headers=headers).json()["email"]
    return db.query(User).filter(User.email == email).one()


@pytest.fixture
def member(client, db, fake_redis):
    headers = register_and_login(client)
    user = _user(client, db, headers)
    db.add(RiskProfile(user_id=user.id, category=RiskCategory.moderate, answers={}))
    db.commit()
    return headers, user


def _note(db, user, minutes_ago=0, read=False, rule="idle_cash") -> Notification:
    when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)
    row = Notification(
        user_id=user.id,
        type={"idle_cash": "buy", "sell_forecast": "sell", "roll_suggested": "roll"}[rule],
        rule=rule,
        strength=None,
        ticker=None,
        reasoning="Rs. 1,000.00 of your portfolio is not invested.",
        params={"amount": "1000.00", "blocked_by": {}, "as_of": "2026-10-23"},
        link="/portfolio",
        dedupe_key=f"test:{uuid.uuid4()}",
        detected_at=when,
        sent_at=when,
        read=read,
        push_status="off",
    )
    db.add(row)
    db.commit()
    return row


def test_every_endpoint_needs_a_login(client):
    for method, path in [
        ("get", "/notifications"),
        ("get", "/notifications/preferences"),
        ("patch", "/notifications/preferences"),
        ("post", "/notifications/read-all"),
        ("post", "/notifications/devices"),
    ]:
        assert getattr(client, method)(path).status_code == 401, path


def test_every_endpoint_needs_a_risk_profile(client, fake_redis):
    headers = register_and_login(client)
    response = client.get("/notifications", headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "risk_profile_required"


def test_settings_start_with_everything_off(client, member):
    headers, _ = member
    body = client.get("/notifications/preferences", headers=headers).json()
    assert body == {
        "buy_enabled": False,
        "sell_enabled": False,
        "roll_enabled": False,
        "push_enabled": False,
        "sensitivity": "all",
        "daily_cap": 3,
        "quiet_hours_enabled": False,
        "quiet_start": "22:00:00",
        "quiet_end": "08:00:00",
        "language": "en",
        "timezone": "Asia/Karachi",
        "push_available": False,
    }


def test_settings_change_only_what_is_sent_and_persist(client, member):
    headers, _ = member
    response = client.patch(
        "/notifications/preferences",
        json={"sell_enabled": True, "daily_cap": 5, "quiet_hours_enabled": True},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    again = client.patch(
        "/notifications/preferences", json={"quiet_start": "23:30"}, headers=headers
    ).json()
    assert (again["sell_enabled"], again["buy_enabled"], again["daily_cap"]) == (True, False, 5)
    assert again["quiet_start"] == "23:30:00"
    assert client.get("/notifications/preferences", headers=headers).json() == again


@pytest.mark.parametrize(
    "body",
    [
        {"daily_cap": 0},
        {"daily_cap": 11},
        {"sensitivity": "loud"},
        {"language": "fr"},
        {"quiet_start": "22:00:30"},
    ],
)
def test_invalid_settings_are_refused(client, member, body):
    headers, _ = member
    assert client.patch("/notifications/preferences", json=body, headers=headers).status_code == 422


def test_quiet_hours_need_different_start_and_end(client, member):
    headers, _ = member
    response = client.patch(
        "/notifications/preferences",
        json={"quiet_hours_enabled": True, "quiet_start": "08:00", "quiet_end": "08:00"},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "quiet_hours_empty"


def test_the_list_is_newest_first_with_the_unread_count_and_pages(client, db, member):
    headers, user = member
    old = _note(db, user, minutes_ago=30)
    middle = _note(db, user, minutes_ago=20, read=True)
    new = _note(db, user, minutes_ago=10)

    first = client.get("/notifications?limit=2", headers=headers).json()
    assert [n["id"] for n in first["items"]] == [str(new.id), str(middle.id)]
    assert first["unread_count"] == 2
    assert first["next_before"] == str(middle.id)
    second = client.get(f"/notifications?limit=2&before={middle.id}", headers=headers).json()
    assert [n["id"] for n in second["items"]] == [str(old.id)]
    assert second["next_before"] is None

    item = first["items"][0]
    assert item["sent_at"].endswith("Z")
    assert item["params"]["amount"] == "1000.00"
    assert item["link"] == "/portfolio"


def test_an_unknown_cursor_is_not_found(client, member):
    headers, _ = member
    response = client.get(f"/notifications?before={uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


def test_mark_one_and_all_as_read(client, db, member):
    headers, user = member
    one, two = _note(db, user), _note(db, user, minutes_ago=1)
    body = client.patch(f"/notifications/{one.id}/read", headers=headers).json()
    assert body["read"] is True and body["read_at"]
    assert client.get("/notifications", headers=headers).json()["unread_count"] == 1
    assert client.post("/notifications/read-all", headers=headers).json() == {"updated": 1}
    assert client.get("/notifications", headers=headers).json()["unread_count"] == 0
    db.refresh(two)
    assert two.read is True


def test_another_users_notifications_are_invisible(client, db, member, fake_redis):
    headers, owner = member
    note = _note(db, owner)
    other_headers = register_and_login(client)
    other = _user(client, db, other_headers)
    db.add(RiskProfile(user_id=other.id, category=RiskCategory.moderate, answers={}))
    db.commit()

    assert client.get("/notifications", headers=other_headers).json()["items"] == []
    assert client.patch(f"/notifications/{note.id}/read", headers=other_headers).status_code == 404
    assert client.post("/notifications/read-all", headers=other_headers).json() == {"updated": 0}
    db.refresh(note)
    assert note.read is False
    other_body = client.get(f"/notifications?before={note.id}", headers=other_headers)
    assert other_body.status_code == 404


def test_devices_register_move_between_accounts_and_delete_only_their_own(
    client, db, member, fake_redis
):
    headers, owner = member
    token = "browser-token-0123456789abcdef"
    created = client.post(
        "/notifications/devices", json={"platform": "web", "token": token}, headers=headers
    )
    assert created.status_code == 201, created.text
    device_id = created.json()["id"]

    other_headers = register_and_login(client)
    other = _user(client, db, other_headers)
    db.add(RiskProfile(user_id=other.id, category=RiskCategory.moderate, answers={}))
    db.commit()
    assert client.delete(
        f"/notifications/devices/{device_id}", headers=other_headers
    ).status_code == (404)

    # The same browser signs in to the other account: the token moves, it is not shared
    moved = client.post(
        "/notifications/devices", json={"platform": "web", "token": token}, headers=other_headers
    ).json()
    assert moved["id"] == device_id
    db.expire_all()
    assert db.get(PushDevice, uuid.UUID(device_id)).user_id == other.id
    assert client.delete(f"/notifications/devices/{device_id}", headers=headers).status_code == 404
    assert client.delete(
        f"/notifications/devices/{device_id}", headers=other_headers
    ).status_code == (204)


@pytest.mark.parametrize(
    "body", [{"platform": "expo", "token": "x" * 30}, {"platform": "web", "token": "short"}]
)
def test_only_web_tokens_of_a_plausible_length_register_for_now(client, member, body):
    headers, _ = member
    assert client.post("/notifications/devices", json=body, headers=headers).status_code == 422


def test_requests_are_rate_limited_per_user(client, member, monkeypatch, fake_redis):
    headers, _ = member
    monkeypatch.setattr(settings, "NOTIFICATIONS_RATE_LIMIT", 2)
    fake_redis.ttls.clear()
    assert client.get("/notifications", headers=headers).status_code == 200
    assert client.get("/notifications/preferences", headers=headers).status_code == 200
    response = client.get("/notifications", headers=headers)
    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "rate_limited"
    assert int(response.headers["Retry-After"]) > 0

    # Another user has a separate allowance
    other_headers = register_and_login(client)
    assert client.get("/notifications", headers=other_headers).status_code == 409
