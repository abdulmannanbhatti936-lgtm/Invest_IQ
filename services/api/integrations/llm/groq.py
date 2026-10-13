"""
Groq chat completions (GroqCloud's OpenAI-compatible endpoint), over plain HTTPS. Backup.

Groq's gpt-oss models reason before answering and count those tokens in `completion_tokens`
against `max_tokens` (checked 2026-10-13: `completion_tokens_details.reasoning_tokens`), so a
reasoning allowance is added to the reply budget and their reasoning effort is set to low. The
allowance is small because the free tier's 8,000 tokens a minute must also hold the prompt.
"""

from integrations.llm.openai_compat import ChatCompletionsProvider


class GroqProvider(ChatCompletionsProvider):
    name = "groq"
    url = "https://api.groq.com/openai/v1/chat/completions"
    reasoning_allowance = 512

    def extra_body(self) -> dict:
        return {"reasoning_effort": "low"} if self.model.startswith("openai/gpt-oss") else {}
