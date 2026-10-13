"""
Steps 8.3 / 8.5: the chat endpoints with a scripted provider (CI never calls a real LLM).
The active-portfolio cases use the Phase 5 worked example (Rs 100,000 Moderate).
"""

import pytest

from core.config import settings
from integrations.llm import LLMRateLimited, LLMResult, LLMUnavailable
from models.chat import ChatMessage
from services import chat_context, chat_prompt, chat_service
from tests import test_portfolio_api
from tests.conftest import register_and_login
from tests.test_chat_context import _user, fake_bundle
from tests.test_portfolio_api import _generate, _with_profile

# The Phase 5 fixtures (Rs 100,000 Moderate worked example), shared with pytest here
investor = test_portfolio_api.investor
worked_example = test_portfolio_api.worked_example

GROUNDED = "Your portfolio cost Rs. 99,887.21 and Rs. 112.79 was left as cash."


class ScriptedProvider:
    """Answers with the scripted texts in order (or raises them) and records every call."""

    name = "scripted"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, turns, *, max_tokens, temperature, deadline, retry=True):
        self.calls.append(
            {"system": system, "turns": turns, "max_tokens": max_tokens, "retry": retry}
        )
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return LLMResult(text=reply, model="scripted-1", input_tokens=1000, output_tokens=50)


@pytest.fixture
def chat(monkeypatch, fake_redis):
    """Chat configured with a scripted provider and the 18-stock fake model bundle."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mistral")
    monkeypatch.setattr(settings, "LLM_MODEL", "scripted-1")
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(chat_context, "_load_bundle", lambda: fake_bundle())

    def install(*replies):
        provider = ScriptedProvider(*replies)
        monkeypatch.setattr(chat_service, "get_providers", lambda: [provider])
        return provider

    return install


@pytest.fixture
def owner(client, investor, worked_example):
    assert _generate(client, investor).status_code == 201
    return investor


def send(client, headers, content="How is my portfolio?", language="en"):
    return client.post(
        "/chat/message", json={"content": content, "language": language}, headers=headers
    )


def test_a_grounded_reply_is_stored_with_its_context_and_sources(client, db, owner, chat):
    provider = chat(GROUNDED)

    response = send(client, owner)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user_message"]["content"] == "How is my portfolio?"
    reply = body["reply"]
    assert reply["content"] == GROUNDED
    assert reply["figure_check"] == "passed"
    assert reply["language"] == "en"
    assert [s["kind"] for s in reply["sources"]] == ["portfolio"]
    assert reply["sources"][0]["date"]

    system = provider.calls[0]["system"]
    assert "Rs. 99,887.21" in system and "Reply in English" in system
    row = db.query(ChatMessage).filter(ChatMessage.id == reply["id"]).one()
    assert row.context_version == "ctx-v2" and len(row.context_hash) == 64
    assert row.context_refs["portfolio_id"]
    assert (row.provider, row.model, row.prompt_version) == ("scripted", "scripted-1", "prompt-v3")
    assert (row.input_tokens, row.output_tokens) == (1000, 50)
    assert row.latency_ms is not None
    assert row.figure_check_detail == {
        "attempts": [
            {
                "provider": "scripted:scripted-1",
                "unmatched": [],
                "number_words": [],
                "truncated": False,
            }
        ],
        "failover": None,
    }


def test_the_system_prompt_never_carries_identity(client, db, owner, chat):
    provider = chat(GROUNDED)
    send(client, owner)
    user = _user(db, client, owner)
    system = provider.calls[0]["system"]
    assert user.email not in system
    assert user.full_name not in system
    assert str(user.id) not in system


def test_a_failed_figure_check_regenerates_once_with_the_figures_named(client, owner, chat):
    provider = chat("Your portfolio cost about Rs. 99,900.", GROUNDED)

    reply = send(client, owner).json()["reply"]

    assert reply["figure_check"] == "regenerated"
    assert reply["content"] == GROUNDED
    assert "CORRECTION" not in provider.calls[0]["system"]
    assert "not in CONTEXT: 99,900" in provider.calls[1]["system"]


@pytest.mark.parametrize(
    "language, content",
    [
        ("en", "How is my portfolio?"),
        ("ur", "میرا پورٹ فولیو کیسا ہے؟"),
        ("ur-latn", "mera portfolio kaisa hai?"),
    ],
)
def test_two_failed_checks_send_the_fallback_in_the_reply_language(
    client, db, owner, chat, language, content
):
    chat("It may grow 12% a year.", "Twenty percent a year is possible.")

    reply = send(client, owner, content, "ur" if language == "ur" else "en").json()["reply"]

    assert reply["figure_check"] == "fallback"
    assert reply["content"] == chat_prompt.FALLBACK[language]
    assert reply["sources"] == []
    row = db.query(ChatMessage).filter(ChatMessage.id == reply["id"]).one()
    attempts = row.figure_check_detail["attempts"]
    assert attempts[0]["unmatched"] == ["12"]
    assert attempts[1]["number_words"] == ["Twenty percent"]


def test_roman_urdu_is_answered_in_roman_urdu_whatever_the_toggle(client, owner, chat):
    provider = chat(GROUNDED)

    body = send(client, owner, "mera portfolio kaisa hai?", "ur").json()

    assert body["user_message"]["language"] == "ur-latn"
    assert body["reply"]["language"] == "ur-latn"
    assert "Reply in Roman Urdu" in provider.calls[0]["system"]


def test_follow_ups_carry_the_last_six_messages(client, owner, chat):
    provider = chat(*[GROUNDED] * 5)
    for i in range(5):
        assert send(client, owner, f"question {i}").status_code == 201

    turns = provider.calls[-1]["turns"]
    # The last 6 stored messages (questions 1-3 with their replies), then the new question
    assert [t.role for t in turns] == ["user", "assistant"] * 3 + ["user"]
    assert [t.content for t in turns if t.role == "user"] == [
        "question 1",
        "question 2",
        "question 3",
        "question 4",
    ]


def test_a_regenerated_portfolio_is_used_on_the_next_message(client, owner, chat):
    provider = chat(GROUNDED, "Your portfolio is based on Rs. 150,000.00.")
    send(client, owner)
    assert _generate(client, owner, capital="150000").status_code == 201

    reply = send(client, owner).json()["reply"]

    assert "Rs. 150,000.00" in provider.calls[1]["system"]
    assert "Rs. 100,000.00" not in provider.calls[1]["system"]
    assert reply["figure_check"] == "passed"


def test_the_eleventh_message_in_five_minutes_is_rate_limited(client, db, owner, chat):
    chat(*[GROUNDED] * 10)
    for _ in range(10):
        assert send(client, owner).status_code == 201

    response = send(client, owner)

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "rate_limited"
    assert int(response.headers["Retry-After"]) == settings.CHAT_LIMIT_WINDOW_SECONDS
    assert db.query(ChatMessage).count() == 20


def test_the_daily_limit_applies_too(client, owner, chat, monkeypatch):
    monkeypatch.setattr(settings, "CHAT_LIMIT_PER_DAY", 2)
    chat(GROUNDED, GROUNDED)
    send(client, owner)
    send(client, owner)
    assert send(client, owner).status_code == 429


def test_the_rate_limit_fails_open_when_redis_is_down(client, owner, chat, monkeypatch):
    def down():
        raise ConnectionError("redis down")

    monkeypatch.setattr(chat_service, "get_redis_client", down)
    chat(GROUNDED)
    assert send(client, owner).status_code == 201


@pytest.mark.parametrize(
    "error, reason, retry_after",
    [(LLMUnavailable("boom"), "provider_error", None), (LLMRateLimited(4.0), "provider_busy", "4")],
)
def test_provider_failure_is_503_and_stores_nothing(
    client, db, owner, chat, error, reason, retry_after
):
    chat(error)

    response = send(client, owner)

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "chat_unavailable",
        "reason": reason,
        "message": "The assistant is not available right now.",
    }
    assert response.headers.get("Retry-After") == retry_after
    assert db.query(ChatMessage).count() == 0


def test_not_configured_is_503_and_history_says_unavailable(
    client, investor, monkeypatch, fake_redis
):
    monkeypatch.setattr(settings, "LLM_MODEL", "")

    response = send(client, investor)

    assert response.status_code == 503
    assert response.json()["detail"]["reason"] == "not_configured"
    history = client.get("/chat/history", headers=investor).json()
    assert history == {
        "messages": [],
        "next_before": None,
        "chat_available": False,
        "unavailable_reason": "not_configured",
    }


def test_the_mock_provider_answers_from_the_context(client, owner, monkeypatch, fake_redis):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(chat_context, "_load_bundle", lambda: fake_bundle())

    reply = send(client, owner).json()["reply"]

    assert reply["content"].startswith("MOCK reply: your portfolio cost Rs. 99,887.21")
    assert reply["figure_check"] == "passed"


def test_no_portfolio_reply_is_grounded_too(client, investor, chat):
    provider = chat("You do not have a portfolio yet. You can make one on the Portfolio screen.")
    reply = send(client, investor).json()["reply"]
    assert reply["figure_check"] == "passed"
    assert '"portfolio":null' in provider.calls[0]["system"]


@pytest.mark.parametrize(
    "body",
    [
        {"content": "", "language": "en"},
        {"content": "   ", "language": "en"},
        {"content": "x" * 1001, "language": "en"},
        {"content": "hi", "language": "fr"},
        {"content": "hi", "language": "ur-latn"},
    ],
)
def test_invalid_messages_are_422(client, investor, body):
    assert client.post("/chat/message", json=body, headers=investor).status_code == 422


def test_every_chat_endpoint_needs_a_login_and_a_risk_profile(client):
    for method, path in [
        ("post", "/chat/message"),
        ("get", "/chat/history"),
        ("delete", "/chat/history"),
    ]:
        kwargs = {"json": {"content": "hi", "language": "en"}} if method == "post" else {}
        assert getattr(client, method)(path, **kwargs).status_code == 401
        no_profile = register_and_login(client)
        response = getattr(client, method)(path, headers=no_profile, **kwargs)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "risk_profile_required"


def _two_users(client, db):
    a, b = register_and_login(client), register_and_login(client)
    _with_profile(db, a, client)
    _with_profile(db, b, client)
    return a, b


def test_a_user_only_ever_sees_and_clears_their_own_messages(client, db, chat):
    a, b = _two_users(client, db)
    chat(*["You do not have a portfolio yet."] * 4)
    for i in range(3):
        send(client, a, f"A question {i}")
    send(client, b, "B question")

    a_history = client.get("/chat/history", headers=a).json()["messages"]
    b_history = client.get("/chat/history", headers=b).json()["messages"]

    assert len(a_history) == 6 and len(b_history) == 2
    assert all("B question" != m["content"] for m in a_history)
    assert [m["content"] for m in b_history if m["role"] == "user"] == ["B question"]
    # A's message id is not a cursor B can use
    cursor = client.get("/chat/history", params={"before": a_history[0]["id"]}, headers=b)
    assert cursor.status_code == 404
    assert cursor.json()["detail"]["code"] == "message_not_found"

    assert client.delete("/chat/history", headers=b).status_code == 204
    assert client.get("/chat/history", headers=b).json()["messages"] == []
    assert len(client.get("/chat/history", headers=a).json()["messages"]) == 6


def test_history_pages_newest_first(client, db, chat):
    a, _ = _two_users(client, db)
    chat(*["You do not have a portfolio yet."] * 3)
    for i in range(3):
        send(client, a, f"question {i}")

    first = client.get("/chat/history", params={"limit": 4}, headers=a).json()
    assert [m["content"] for m in first["messages"] if m["role"] == "user"] == [
        "question 2",
        "question 1",
    ]
    assert first["messages"][0]["role"] == "assistant"
    assert first["chat_available"] is True
    second = client.get(
        "/chat/history", params={"limit": 4, "before": first["next_before"]}, headers=a
    ).json()
    assert [m["role"] for m in second["messages"]] == ["assistant", "user"]
    assert second["messages"][1]["content"] == "question 0"
    assert second["next_before"] is None


def test_message_text_is_never_logged(client, owner, chat, caplog):
    chat("Your portfolio cost about Rs. 99,900.", GROUNDED)
    with caplog.at_level("DEBUG"):
        send(client, owner, "my secret question about HBL")
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "my secret question" not in logged
    assert "99,900" not in logged and "99,887.21" not in logged
