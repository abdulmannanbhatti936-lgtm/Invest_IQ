"""
The chat-completions request and reply shape that Mistral and Groq share (the OpenAI-style
`/chat/completions` endpoint), so each of those adapters only names its URL.
"""

from integrations.llm.base import LLMResult, LLMUnavailable, Provider, post_json


class ChatCompletionsProvider(Provider):
    url: str

    def __init__(self, api_key: str, model: str):
        self._key = api_key
        self.model = model

    def complete(
        self, system, turns, *, max_tokens, temperature, deadline, retry=True
    ) -> LLMResult:
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
        data = post_json(self.url, headers, body, deadline, self.name, retry)
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMUnavailable("unexpected response shape") from e
        if not isinstance(text, str) or not text.strip():
            raise LLMUnavailable("empty reply")
        usage = data.get("usage") or {}
        return LLMResult(
            text=text.strip(),
            model=data.get("model") or self.model,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            truncated=choice.get("finish_reason") == "length",
        )
