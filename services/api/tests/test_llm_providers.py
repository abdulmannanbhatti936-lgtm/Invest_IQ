"""
LLM adapters: request shapes, reply parsing and the shared HTTP policy (timeouts, one retry,
Retry-After, the one-call-per-second slot, 429 counting). No real provider is ever called:
httpx.post is replaced by scripted responses.
"""

import time

import httpx
import pytest
from pydantic import ValidationError

from core.config import Settings, settings
from integrations import llm
from integrations.llm import base
from integrations.llm.base import LLMBusy, LLMError, Turn
from integrations.llm.claude import ClaudeProvider
from integrations.llm.mistral import MistralProvider

MISTRAL_OK = {
    "model": "mistral-test-2601",
    "choices": [{"message": {"role": "assistant", "content": "  Your portfolio cost Rs. 1.00. "}}],
    "usage": {"prompt_tokens": 1200, "completion_tokens": 80},
}
CLAUDE_OK = {
    "model": "claude-test",
    "content": [{"type": "text", "text": "Hello"}],
    "usage": {"input_tokens": 900, "output_tokens": 12},
}


class Script:
    """Replaces httpx.post: returns the scripted responses in order and records each call."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        status, body, extra_headers = item
        return httpx.Response(status, json=body, headers=extra_headers or {})


@pytest.fixture
def http(monkeypatch, fake_redis):
    sleeps = []
    monkeypatch.setattr(base.time, "sleep", lambda s: sleeps.append(s))

    def install(*responses):
        script = Script(*responses)
        script.sleeps = sleeps
        monkeypatch.setattr(base.httpx, "post", script)
        # Each test starts with a free call slot
        fake_redis.store.pop(base.SLOT_KEY, None)
        return script

    return install


def _mistral_call(deadline_s=45):
    return MistralProvider("key-123", "mistral-test-2601").complete(
        "SYSTEM",
        [Turn("user", "hi"), Turn("assistant", "hello"), Turn("user", "and now?")],
        max_tokens=700,
        temperature=0.2,
        deadline=time.monotonic() + deadline_s,
    )


def test_mistral_request_and_reply(http):
    script = http((200, MISTRAL_OK, None))

    result = _mistral_call()

    call = script.calls[0]
    assert call["url"] == "https://api.mistral.ai/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer key-123"
    assert call["json"]["model"] == "mistral-test-2601"
    assert [m["role"] for m in call["json"]["messages"]] == ["system", "user", "assistant", "user"]
    assert call["json"]["messages"][0]["content"] == "SYSTEM"
    assert (call["json"]["max_tokens"], call["json"]["temperature"]) == (700, 0.2)
    assert call["timeout"].connect == 5.0 and call["timeout"].read == 25.0
    assert result.text == "Your portfolio cost Rs. 1.00."
    assert (result.model, result.input_tokens, result.output_tokens) == (
        "mistral-test-2601",
        1200,
        80,
    )


def test_claude_request_and_reply(http):
    script = http((200, CLAUDE_OK, None))

    result = ClaudeProvider("ck", "claude-test").complete(
        "SYSTEM",
        [Turn("user", "hi")],
        max_tokens=700,
        temperature=0.2,
        deadline=time.monotonic() + 45,
    )

    call = script.calls[0]
    assert call["url"] == "https://api.anthropic.com/v1/messages"
    assert call["headers"] == {"x-api-key": "ck", "anthropic-version": "2023-06-01"}
    assert call["json"]["system"] == "SYSTEM"
    assert call["json"]["messages"] == [{"role": "user", "content": "hi"}]
    assert (result.text, result.input_tokens, result.output_tokens) == ("Hello", 900, 12)


def test_a_429_is_counted_and_retried_after_retry_after(http, fake_redis):
    script = http((429, {}, {"Retry-After": "3"}), (200, MISTRAL_OK, None))

    assert _mistral_call().text.startswith("Your portfolio")

    assert len(script.calls) == 2
    assert 3.0 in script.sleeps
    assert [v for k, v in fake_redis.store.items() if k.startswith("chat:provider_429:")] == ["1"]


def test_retry_after_is_capped_at_5_seconds(http):
    script = http((429, {}, {"Retry-After": "60"}), (200, MISTRAL_OK, None))
    _mistral_call()
    assert 5.0 in script.sleeps and 60.0 not in script.sleeps


def test_two_429s_mean_busy_with_the_providers_wait(http):
    http((429, {}, {"Retry-After": "4"}), (429, {}, {"Retry-After": "4"}))
    with pytest.raises(LLMBusy) as caught:
        _mistral_call()
    assert caught.value.reason == "provider_busy"
    assert caught.value.retry_after == 4.0


def test_a_timeout_or_5xx_is_retried_once_then_fails(http):
    script = http(httpx.ReadTimeout("slow"), (502, {}, None))
    with pytest.raises(LLMError) as caught:
        _mistral_call()
    assert caught.value.reason == "provider_error"
    assert len(script.calls) == 2
    assert 2.0 in script.sleeps


def test_a_5xx_then_success_returns_the_reply(http):
    http((503, {}, None), (200, MISTRAL_OK, None))
    assert _mistral_call().output_tokens == 80


def test_a_bad_key_is_not_retried(http):
    script = http((401, {"message": "Unauthorized"}, None))
    with pytest.raises(LLMError):
        _mistral_call()
    assert len(script.calls) == 1


def test_no_retry_when_the_deadline_leaves_no_room(http):
    script = http((503, {}, None), (200, MISTRAL_OK, None))
    with pytest.raises(LLMError):
        _mistral_call(deadline_s=2.5)
    assert len(script.calls) == 1


def test_an_empty_or_malformed_reply_is_an_error(http):
    http((200, {"choices": [{"message": {"content": "   "}}]}, None))
    with pytest.raises(LLMError):
        _mistral_call()
    http((200, {"unexpected": True}, None))
    with pytest.raises(LLMError):
        _mistral_call()


def test_calls_wait_for_the_one_per_second_slot(http, fake_redis, monkeypatch):
    script = http((200, MISTRAL_OK, None))
    waited = []
    real_set = fake_redis.set

    def set_after_two_tries(key, value, **kwargs):
        waited.append(key)
        if len(waited) < 3:
            return None
        return real_set(key, value, **kwargs)

    monkeypatch.setattr(fake_redis, "set", set_after_two_tries)
    _mistral_call()
    # Taken twice by another call, free on the third try: two 0.1 s waits, then the call
    assert len(waited) == 3
    assert script.sleeps == [0.1, 0.1]
    assert len(script.calls) == 1


def test_get_provider_follows_configuration(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MODEL", "mistral-test-2601")
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "real-key")
    assert isinstance(llm.get_provider(), MistralProvider)

    monkeypatch.setattr(settings, "LLM_PROVIDER", "claude")
    monkeypatch.setattr(settings, "CLAUDE_API_KEY", "placeholder_claude_api_key")
    with pytest.raises(llm.LLMNotConfigured, match="CLAUDE_API_KEY is not set"):
        llm.get_provider()
    monkeypatch.setattr(settings, "CLAUDE_API_KEY", "ck-real")
    assert isinstance(llm.get_provider(), ClaudeProvider)


def test_missing_model_or_key_makes_chat_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mistral")
    monkeypatch.setattr(settings, "LLM_MODEL", "")
    assert settings.chat_unavailable_reason() == "LLM_MODEL is not set"
    monkeypatch.setattr(settings, "LLM_MODEL", "mistral-test-2601")
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "")
    assert settings.chat_unavailable_reason() == "MISTRAL_API_KEY is not set"
    with pytest.raises(llm.LLMNotConfigured) as caught:
        llm.get_provider()
    assert caught.value.reason == "not_configured"


def test_the_mock_provider_is_refused_outside_development():
    secrets = {"JWT_SECRET": "a" * 40, "JWT_REFRESH_SECRET": "b" * 40}
    with pytest.raises(ValidationError, match="LLM_PROVIDER=mock"):
        Settings(ENVIRONMENT="production", LLM_PROVIDER="mock", **secrets)
    assert (
        Settings(ENVIRONMENT="development", LLM_PROVIDER="mock", **secrets).LLM_PROVIDER == "mock"
    )


def test_tests_can_never_reach_a_provider():
    with pytest.raises(RuntimeError, match="LLM network calls are disabled"):
        base.httpx.post("https://api.mistral.ai/v1/chat/completions")
