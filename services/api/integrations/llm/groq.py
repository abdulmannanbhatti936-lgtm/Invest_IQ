"""
Groq chat completions (GroqCloud's OpenAI-compatible endpoint), over plain HTTPS.

Groq's gpt-oss models reason before answering and count those tokens in `completion_tokens`
against `max_tokens` (checked 2026-10-13: `completion_tokens_details.reasoning_tokens`), so a
reasoning allowance is added to the reply budget and their reasoning effort is set to low.

The free tier also refuses any single request whose input plus `max_tokens` exceeds its 8,000
tokens a minute (HTTP 413, seen on an Urdu message in the 2026-10-14 adversarial run: about
6,441 input tokens plus 1,712 requested). So `max_tokens` is capped to what fits, using Groq's
own measured ratio of 3.40 characters per token on our prompts (21,905 characters were 6,441
tokens in Urdu and 20,351 were 5,981 in English) and a 200-token margin.
"""

from integrations.llm.openai_compat import ChatCompletionsProvider

REQUEST_TOKEN_CAP = 8_000
CHARS_PER_TOKEN = 3.40
MARGIN_TOKENS = 200
# Never ask for less than this; a reply that needs more stops at the limit and is regenerated
MIN_REQUEST_OUTPUT = 300


class GroqProvider(ChatCompletionsProvider):
    name = "groq"
    url = "https://api.groq.com/openai/v1/chat/completions"
    reasoning_allowance = 512

    def extra_body(self) -> dict:
        return {"reasoning_effort": "low"} if self.model.startswith("openai/gpt-oss") else {}

    def output_tokens(self, system: str, turns, max_tokens: int) -> int:
        chars = len(system) + sum(len(t.content) for t in turns)
        room = REQUEST_TOKEN_CAP - int(chars / CHARS_PER_TOKEN) - MARGIN_TOKENS
        return max(MIN_REQUEST_OUTPUT, min(max_tokens + self.reasoning_allowance, room))
