"""
Google Gemini API (`models.generateContent`), over plain HTTPS with httpx. The primary chat
provider since 2026-10-13.

Gemini 3 models always think before answering, and their thinking tokens count against
`maxOutputTokens` (ai.google.dev/gemini-api/docs/thinking). The app's reply budget is for the
visible reply, so the thinking allowance is added on top; a reply that still stops at the
limit with no text is treated as no reply.
"""

from integrations.llm.base import LLMResult, LLMUnavailable, Provider, post_json

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
THINKING_ALLOWANCE_TOKENS = 2048


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self._key = api_key
        self.model = model

    def complete(
        self, system, turns, *, max_tokens, temperature, deadline, retry=True
    ) -> LLMResult:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                # Gemini calls the assistant's turns "model"
                {
                    "role": "model" if t.role == "assistant" else "user",
                    "parts": [{"text": t.content}],
                }
                for t in turns
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens + THINKING_ALLOWANCE_TOKENS,
                "candidateCount": 1,
            },
        }
        headers = {"x-goog-api-key": self._key, "Accept": "application/json"}
        url = f"{BASE_URL}/{self.model}:generateContent"
        data = post_json(url, headers, body, deadline, self.name, retry)

        blocked = (data.get("promptFeedback") or {}).get("blockReason")
        if blocked:
            raise LLMUnavailable(f"prompt blocked: {blocked}")
        try:
            candidate = data["candidates"][0]
            parts = (candidate.get("content") or {}).get("parts") or []
            # Thought summaries, when a model returns them, are not part of the reply
            text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except (KeyError, IndexError, TypeError, AttributeError) as e:
            raise LLMUnavailable("unexpected response shape") from e
        if not text.strip():
            raise LLMUnavailable(f"empty reply (finishReason {candidate.get('finishReason')})")
        usage = data.get("usageMetadata") or {}
        output = usage.get("candidatesTokenCount")
        thoughts = usage.get("thoughtsTokenCount")
        return LLMResult(
            text=text.strip(),
            model=data.get("modelVersion") or self.model,
            input_tokens=usage.get("promptTokenCount"),
            # Thinking tokens are billed and limited as output, so they are counted as output
            output_tokens=(
                None if output is None and thoughts is None else (output or 0) + (thoughts or 0)
            ),
            truncated=candidate.get("finishReason") == "MAX_TOKENS",
        )
