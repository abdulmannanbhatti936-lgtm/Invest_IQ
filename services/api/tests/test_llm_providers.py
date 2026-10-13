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
from integrations.llm import base, claude, gemini
from integrations.llm.base import LLMRateLimited, LLMUnavailable, Turn
from integrations.llm.claude import ClaudeProvider
from integrations.llm.gemini import THINKING_ALLOWANCE_TOKENS, GeminiProvider
from integrations.llm.groq import GroqProvider
from integrations.llm.mistral import MistralProvider
from tests.conftest import LLM_HOSTS

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
    with pytest.raises(LLMRateLimited) as caught:
        _mistral_call()
    assert caught.value.reason == "provider_busy"
    assert caught.value.retry_after == 4.0


def test_a_timeout_or_5xx_is_retried_once_then_fails(http):
    script = http(httpx.ReadTimeout("slow"), (502, {}, None))
    with pytest.raises(LLMUnavailable) as caught:
        _mistral_call()
    assert caught.value.reason == "provider_error"
    assert len(script.calls) == 2
    assert 2.0 in script.sleeps


def test_a_5xx_then_success_returns_the_reply(http):
    http((503, {}, None), (200, MISTRAL_OK, None))
    assert _mistral_call().output_tokens == 80


def test_a_bad_key_is_not_retried(http):
    script = http((401, {"message": "Unauthorized"}, None))
    with pytest.raises(LLMUnavailable):
        _mistral_call()
    assert len(script.calls) == 1


def test_no_retry_when_the_deadline_leaves_no_room(http):
    script = http((503, {}, None), (200, MISTRAL_OK, None))
    with pytest.raises(LLMUnavailable):
        _mistral_call(deadline_s=2.5)
    assert len(script.calls) == 1


def test_an_empty_or_malformed_reply_is_an_error(http):
    http((200, {"choices": [{"message": {"content": "   "}}]}, None))
    with pytest.raises(LLMUnavailable):
        _mistral_call()
    http((200, {"unexpected": True}, None))
    with pytest.raises(LLMUnavailable):
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
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mistral")
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


@pytest.mark.parametrize("host", LLM_HOSTS)
def test_tests_can_never_reach_a_provider(host):
    with pytest.raises(RuntimeError, match="LLM network calls are disabled"):
        base.httpx.post(f"https://{host}/v1/anything")


def test_every_adapter_calls_one_of_the_blocked_hosts():
    for url in (gemini.BASE_URL, GroqProvider.url, MistralProvider.url, claude.URL):
        assert any(url.startswith(f"https://{host}/") for host in LLM_HOSTS), url


def test_the_default_provider_is_gemini_and_each_provider_needs_its_key(monkeypatch):
    assert type(settings).model_fields["LLM_PROVIDER"].default == "gemini"
    monkeypatch.setattr(settings, "LLM_MODEL", "some-model")
    for provider, key_name, adapter in [
        ("gemini", "GEMINI_API_KEY", GeminiProvider),
        ("groq", "GROQ_API_KEY", GroqProvider),
    ]:
        monkeypatch.setattr(settings, "LLM_PROVIDER", provider)
        monkeypatch.setattr(settings, key_name, "")
        assert settings.chat_unavailable_reason() == f"{key_name} is not set"
        monkeypatch.setattr(settings, key_name, "real-key")
        assert isinstance(llm.get_provider(), adapter)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    assert "not a supported provider" in settings.chat_unavailable_reason()


# Gemini (models.generateContent)

GEMINI_OK = {
    "candidates": [
        {
            "content": {
                "role": "model",
                "parts": [
                    {"text": "planning the answer", "thought": True},
                    {"text": " Your portfolio cost Rs. 1.00. "},
                ],
            },
            "finishReason": "STOP",
        }
    ],
    "usageMetadata": {
        "promptTokenCount": 6100,
        "candidatesTokenCount": 90,
        "thoughtsTokenCount": 410,
        "totalTokenCount": 6600,
    },
    "modelVersion": "gemini-test-flash",
}


def _gemini_call():
    return GeminiProvider("gk-1", "gemini-test-flash").complete(
        "SYSTEM",
        [Turn("user", "hi"), Turn("assistant", "hello"), Turn("user", "and now?")],
        max_tokens=700,
        temperature=0.2,
        deadline=time.monotonic() + 45,
    )


def test_gemini_request_and_reply(http):
    script = http((200, GEMINI_OK, None))

    result = _gemini_call()

    call = script.calls[0]
    assert call["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-test-flash:generateContent"
    )
    # The key travels in a header, never in the URL (where it could reach logs)
    assert call["headers"]["x-goog-api-key"] == "gk-1"
    assert "key=" not in call["url"]
    body = call["json"]
    assert body["systemInstruction"] == {"parts": [{"text": "SYSTEM"}]}
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
    assert body["contents"][1]["parts"] == [{"text": "hello"}]
    assert body["generationConfig"] == {
        "temperature": 0.2,
        "maxOutputTokens": 700 + THINKING_ALLOWANCE_TOKENS,
        "candidateCount": 1,
    }
    assert call["timeout"].connect == 5.0 and call["timeout"].read == 25.0
    # Thought parts are not the reply; thinking tokens count as output tokens
    assert result.text == "Your portfolio cost Rs. 1.00."
    assert (result.model, result.input_tokens, result.output_tokens) == (
        "gemini-test-flash",
        6100,
        500,
    )


def test_gemini_429_is_counted_and_retried_then_rate_limited(http, fake_redis):
    script = http((429, {"error": {"code": 429}}, {"Retry-After": "2"}), (200, GEMINI_OK, None))
    assert _gemini_call().text.startswith("Your portfolio")
    assert len(script.calls) == 2 and 2.0 in script.sleeps
    assert [v for k, v in fake_redis.store.items() if k.startswith("chat:provider_429:")] == ["1"]

    http((429, {}, {"Retry-After": "3"}), (429, {}, {"Retry-After": "3"}))
    with pytest.raises(LLMRateLimited) as caught:
        _gemini_call()
    assert caught.value.retry_after == 3.0 and caught.value.reason == "provider_busy"


def test_gemini_5xx_or_timeout_is_retried_once(http):
    http((503, {}, None), (200, GEMINI_OK, None))
    assert _gemini_call().output_tokens == 500
    script = http(httpx.ConnectTimeout("down"), (500, {}, None))
    with pytest.raises(LLMUnavailable) as caught:
        _gemini_call()
    assert caught.value.reason == "provider_error" and len(script.calls) == 2


THOUGHT_ONLY = {
    "content": {"parts": [{"text": "...", "thought": True}]},
    "finishReason": "MAX_TOKENS",
}


@pytest.mark.parametrize(
    "body, message",
    [
        ({"unexpected": True}, "unexpected response shape"),
        ({"candidates": []}, "unexpected response shape"),
        ({"promptFeedback": {"blockReason": "SAFETY"}}, "prompt blocked: SAFETY"),
        ({"candidates": [THOUGHT_ONLY]}, "finishReason MAX_TOKENS"),
        ({"candidates": [{"finishReason": "SAFETY"}]}, "finishReason SAFETY"),
    ],
)
def test_gemini_malformed_blocked_or_empty_replies_are_unavailable(http, body, message):
    http((200, body, None))
    with pytest.raises(LLMUnavailable, match=message):
        _gemini_call()


def test_gemini_bad_key_is_not_retried(http):
    script = http((400, {"error": {"status": "INVALID_ARGUMENT"}}, None))
    with pytest.raises(LLMUnavailable):
        _gemini_call()
    assert len(script.calls) == 1


# Groq (OpenAI-compatible chat completions)

GROQ_OK = {
    "model": "groq-test-120b",
    "choices": [{"message": {"role": "assistant", "content": "Rs. 1.00 in total."}}],
    "usage": {"prompt_tokens": 6000, "completion_tokens": 70},
}


def _groq_call():
    return GroqProvider("gq-1", "openai/gpt-oss-test").complete(
        "SYSTEM",
        [Turn("user", "hi")],
        max_tokens=700,
        temperature=0.2,
        deadline=time.monotonic() + 45,
    )


def test_groq_request_and_reply(http):
    script = http((200, GROQ_OK, None))

    result = _groq_call()

    call = script.calls[0]
    assert call["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer gq-1"
    assert call["json"]["messages"] == [
        {"role": "system", "content": "SYSTEM"},
        {"role": "user", "content": "hi"},
    ]
    # gpt-oss reasons first: a reasoning allowance on top of the reply, at low effort
    assert call["json"]["max_tokens"] == 700 + GroqProvider.reasoning_allowance
    assert (call["json"]["temperature"], call["json"]["reasoning_effort"]) == (0.2, "low")
    assert (result.text, result.model, result.input_tokens, result.output_tokens) == (
        "Rs. 1.00 in total.",
        "groq-test-120b",
        6000,
        70,
    )


def test_groq_429_is_retried_after_retry_after_then_rate_limited(http):
    script = http((429, {}, {"Retry-After": "1"}), (200, GROQ_OK, None))
    assert _groq_call().output_tokens == 70 and 1.0 in script.sleeps
    http((429, {}, None), (429, {}, None))
    with pytest.raises(LLMRateLimited):
        _groq_call()


def test_groq_5xx_then_timeout_is_unavailable(http):
    script = http((502, {}, None), httpx.ReadTimeout("slow"))
    with pytest.raises(LLMUnavailable) as caught:
        _groq_call()
    assert caught.value.reason == "provider_error" and len(script.calls) == 2


@pytest.mark.parametrize(
    "body",
    [{"choices": [{"message": {}}]}, {"choices": []}, {"choices": [{"message": {"content": " "}}]}],
)
def test_groq_malformed_or_empty_replies_are_unavailable(http, body):
    http((200, body, None))
    with pytest.raises(LLMUnavailable):
        _groq_call()


# Finish reasons, the retry switch and failover flags (decided 2026-10-13)


def test_a_reply_cut_off_at_the_token_limit_is_flagged(http):
    cut = {
        "candidates": [
            {"content": {"parts": [{"text": "Your portfolio"}]}, "finishReason": "MAX_TOKENS"}
        ],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 700},
    }
    http((200, cut, None))
    assert _gemini_call().truncated is True
    http((200, GEMINI_OK, None))
    assert _gemini_call().truncated is False

    long_groq = {
        **GROQ_OK,
        "choices": [{"message": {"content": "Rs. 1"}, "finish_reason": "length"}],
    }
    http((200, long_groq, None))
    assert _groq_call().truncated is True
    http(
        (
            200,
            {**GROQ_OK, "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]},
            None,
        )
    )
    assert _groq_call().truncated is False

    http((200, {**CLAUDE_OK, "stop_reason": "max_tokens"}, None))
    result = ClaudeProvider("ck", "claude-test").complete(
        "S", [Turn("user", "hi")], max_tokens=700, temperature=0.2, deadline=time.monotonic() + 45
    )
    assert result.truncated is True


def test_retry_false_makes_one_attempt_for_the_backup_to_take_over(http):
    script = http((503, {}, None), (200, GEMINI_OK, None))
    with pytest.raises(LLMUnavailable) as caught:
        GeminiProvider("gk", "gemini-test-flash").complete(
            "S", [Turn("user", "hi")], max_tokens=700, temperature=0.2,
            deadline=time.monotonic() + 45, retry=False,
        )  # fmt: skip
    assert len(script.calls) == 1 and script.sleeps == []
    assert caught.value.failover is True


@pytest.mark.parametrize(
    "responses, failover",
    [
        (((429, {}, None), (429, {}, None)), True),
        (((502, {}, None), (503, {}, None)), True),
        ((httpx.ReadTimeout("slow"), httpx.ConnectTimeout("down")), True),
        (((400, {}, None),), False),
        (((401, {}, None),), False),
        (((200, {"unexpected": True}, None),), False),
    ],
)
def test_only_429_5xx_and_timeouts_may_fail_over(http, responses, failover):
    http(*responses)
    with pytest.raises(LLMUnavailable) as caught:
        _groq_call()
    assert caught.value.failover is failover


def test_the_last_rate_limit_headers_are_kept_per_provider(http):
    headers = {"x-ratelimit-remaining-tokens": "1200", "x-ratelimit-reset-tokens": "40.5s"}
    http((200, GROQ_OK, headers))
    _groq_call()
    assert base.RATE_LIMIT_HEADERS["groq"]["x-ratelimit-remaining-tokens"] == "1200"
    assert base.RATE_LIMIT_HEADERS["groq"]["x-ratelimit-reset-tokens"] == "40.5s"


def test_only_groqs_gpt_oss_models_get_a_reasoning_effort(http):
    script = http((200, GROQ_OK, None), (200, MISTRAL_OK, None))
    GroqProvider("gq", "qwen/qwen-test").complete(
        "S", [Turn("user", "hi")], max_tokens=700, temperature=0.2, deadline=time.monotonic() + 45
    )
    _mistral_call()
    assert "reasoning_effort" not in script.calls[0]["json"]
    assert script.calls[0]["json"]["max_tokens"] == 700 + GroqProvider.reasoning_allowance
    assert "reasoning_effort" not in script.calls[1]["json"]
    assert script.calls[1]["json"]["max_tokens"] == 700
