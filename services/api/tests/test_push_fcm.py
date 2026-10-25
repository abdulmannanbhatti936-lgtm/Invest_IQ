"""
Phase 7: the FCM web push channel, with the HTTP call faked (tests never reach Firebase), and the
rule that the service account file must sit outside the repository.
"""

import httpx
import pytest

from core.config import REPO_ROOT, Settings, settings
from integrations.push import PushMessage
from integrations.push.fcm import FcmWebChannel

MESSAGE = PushMessage(title="T", body="B", link="/stocks/HBL", tag="investiq-1", data={"a": "1"})


@pytest.fixture
def channel(monkeypatch):
    fcm = FcmWebChannel()
    monkeypatch.setattr(fcm, "_access", lambda: ("access-token", "demo-project"))
    return fcm


def _respond(monkeypatch, status, payload=None, calls=None):
    def post(url, json, headers, timeout):
        if calls is not None:
            calls.append((url, json, headers))
        return httpx.Response(status, json=payload or {}, request=httpx.Request("POST", url))

    monkeypatch.setattr("integrations.push.fcm.httpx.post", post)


def test_a_data_only_message_goes_to_the_v1_endpoint(channel, monkeypatch):
    calls = []
    _respond(monkeypatch, 200, {"name": "projects/demo-project/messages/1"}, calls)
    assert channel.send("device-token", MESSAGE).delivered
    [(url, body, headers)] = calls
    assert url == "https://fcm.googleapis.com/v1/projects/demo-project/messages:send"
    assert headers["Authorization"] == "Bearer access-token"
    message = body["message"]
    assert message["token"] == "device-token"
    assert "notification" not in message  # the service worker draws it
    assert message["data"] == {
        "a": "1",
        "title": "T",
        "body": "B",
        "link": "/stocks/HBL",
        "tag": "investiq-1",
    }
    assert all(isinstance(v, str) for v in message["data"].values())


def test_an_unregistered_token_is_reported_as_dead(channel, monkeypatch):
    payload = {"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}}
    _respond(monkeypatch, 404, payload)
    result = channel.send("old-token", MESSAGE)
    assert (result.delivered, result.token_invalid) == (False, True)
    assert result.detail == "http_404:UNREGISTERED"


def test_a_server_error_keeps_the_token(channel, monkeypatch):
    _respond(monkeypatch, 503, {"error": {"status": "UNAVAILABLE"}})
    result = channel.send("token", MESSAGE)
    assert (result.delivered, result.token_invalid, result.detail) == (
        False,
        False,
        "http_503:unknown",
    )


def test_a_network_failure_never_raises(channel, monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectTimeout("slow")

    monkeypatch.setattr("integrations.push.fcm.httpx.post", fail)
    assert channel.send("token", MESSAGE).detail == "network:ConnectTimeout"


def test_a_sign_in_failure_never_raises_nor_names_the_file(monkeypatch, caplog):
    fcm = FcmWebChannel()
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_FILE", "C:/secret/place/key.json")
    result = fcm.send("token", MESSAGE)
    assert not result.delivered and result.detail.startswith("auth_failed:")
    assert "secret" not in caplog.text


def _settings(path: str) -> Settings:
    return Settings(
        JWT_SECRET="x" * 40,
        JWT_REFRESH_SECRET="y" * 40,
        ENVIRONMENT="development",
        FIREBASE_SERVICE_ACCOUNT_FILE=path,
    )


def test_push_is_off_without_a_file_or_with_a_placeholder():
    assert _settings("").push_unavailable_reason() == "not_configured"
    assert _settings("placeholder_path").push_unavailable_reason() == "not_configured"


def test_a_key_file_inside_the_repository_is_refused():
    inside = REPO_ROOT / "services" / "api" / "firebase-service-account.json"
    assert _settings(str(inside)).push_unavailable_reason() == "file_inside_repository"


def test_a_missing_file_and_a_file_outside_the_repository(tmp_path):
    assert _settings(str(tmp_path / "nope.json")).push_unavailable_reason() == "file_not_found"
    key = tmp_path / "key.json"
    key.write_text("{}")
    assert _settings(str(key)).push_unavailable_reason() is None
