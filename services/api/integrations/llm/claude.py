"""
Claude Messages API, called over plain HTTPS with httpx. Ready for when the project moves from
Mistral's free tier to the Claude API named in Architecture.md §6.4: set LLM_PROVIDER=claude,
LLM_MODEL and CLAUDE_API_KEY.
"""

from integrations.llm.base import LLMError, LLMResult, Provider, post_json

URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class ClaudeProvider(Provider):
    name = "claude"

    def __init__(self, api_key: str, model: str):
        self._key = api_key
        self.model = model

    def complete(self, system, turns, *, max_tokens, temperature, deadline) -> LLMResult:
        body = {
            "model": self.model,
            "system": system,
            "messages": [{"role": t.role, "content": t.content} for t in turns],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {"x-api-key": self._key, "anthropic-version": API_VERSION}
        data = post_json(URL, headers, body, deadline, self.name)
        try:
            text = "".join(block["text"] for block in data["content"] if block["type"] == "text")
        except (KeyError, TypeError) as e:
            raise LLMError("unexpected response shape") from e
        if not text.strip():
            raise LLMError("empty reply")
        usage = data.get("usage") or {}
        return LLMResult(
            text=text.strip(),
            model=data.get("model") or self.model,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )
