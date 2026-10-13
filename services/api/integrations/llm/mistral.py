"""Mistral chat completions (La Plateforme), called over plain HTTPS with httpx."""

from integrations.llm.base import LLMError, LLMResult, Provider, post_json

URL = "https://api.mistral.ai/v1/chat/completions"


class MistralProvider(Provider):
    name = "mistral"

    def __init__(self, api_key: str, model: str):
        self._key = api_key
        self.model = model

    def complete(self, system, turns, *, max_tokens, temperature, deadline) -> LLMResult:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                *({"role": t.role, "content": t.content} for t in turns),
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {self._key}", "Accept": "application/json"}
        data = post_json(URL, headers, body, deadline, self.name)
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError("unexpected response shape") from e
        if not isinstance(text, str) or not text.strip():
            raise LLMError("empty reply")
        usage = data.get("usage") or {}
        return LLMResult(
            text=text.strip(),
            model=data.get("model") or self.model,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )
