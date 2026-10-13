"""
LLM provider adapters for the chatbot (Architecture.md §6.4). The provider and model come from
configuration only (LLM_PROVIDER, LLM_MODEL and the provider's API key), so moving from
Mistral to Claude is a change to .env, not to code.
"""

from core.config import settings
from integrations.llm.base import LLMBusy, LLMError, LLMResult, Provider, Turn
from integrations.llm.claude import ClaudeProvider
from integrations.llm.mistral import MistralProvider
from integrations.llm.mock import MockProvider


class LLMNotConfigured(LLMError):
    reason = "not_configured"


def get_provider() -> Provider:
    problem = settings.chat_unavailable_reason()
    if problem:
        raise LLMNotConfigured(problem)
    if settings.LLM_PROVIDER == "mock":
        return MockProvider()
    adapter = {"mistral": MistralProvider, "claude": ClaudeProvider}[settings.LLM_PROVIDER]
    return adapter(settings.llm_api_key, settings.LLM_MODEL)


__all__ = [
    "LLMBusy",
    "LLMError",
    "LLMNotConfigured",
    "LLMResult",
    "Provider",
    "Turn",
    "get_provider",
]
