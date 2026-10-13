"""Groq chat completions (GroqCloud's OpenAI-compatible endpoint), over plain HTTPS. Backup."""

from integrations.llm.openai_compat import ChatCompletionsProvider


class GroqProvider(ChatCompletionsProvider):
    name = "groq"
    url = "https://api.groq.com/openai/v1/chat/completions"
