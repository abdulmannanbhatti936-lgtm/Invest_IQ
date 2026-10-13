"""Mistral chat completions (La Plateforme), over plain HTTPS. An optional config switch."""

from integrations.llm.openai_compat import ChatCompletionsProvider


class MistralProvider(ChatCompletionsProvider):
    name = "mistral"
    url = "https://api.mistral.ai/v1/chat/completions"
