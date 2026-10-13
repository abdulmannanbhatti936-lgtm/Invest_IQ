"""
LLM provider adapters for the chatbot (Architecture.md §6.4). The provider and model come from
configuration only (LLM_PROVIDER, LLM_MODEL and the provider's API key): Gemini is the default,
Groq the backup, Mistral and Claude optional, so switching is a change to .env, not to code.
"""

from core.config import settings
from integrations.llm.base import LLMRateLimited, LLMResult, LLMUnavailable, Provider, Turn
from integrations.llm.claude import ClaudeProvider
from integrations.llm.gemini import GeminiProvider
from integrations.llm.groq import GroqProvider
from integrations.llm.mistral import MistralProvider
from integrations.llm.mock import MockProvider

ADAPTERS: dict[str, type[Provider]] = {
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "mistral": MistralProvider,
    "claude": ClaudeProvider,
}


class LLMNotConfigured(LLMUnavailable):
    reason = "not_configured"


def provider_for(name: str, model: str, api_key: str) -> Provider:
    return ADAPTERS[name](api_key, model)


def get_provider() -> Provider:
    problem = settings.chat_unavailable_reason()
    if problem:
        raise LLMNotConfigured(problem)
    if settings.LLM_PROVIDER == "mock":
        return MockProvider()
    return provider_for(settings.LLM_PROVIDER, settings.LLM_MODEL, settings.llm_api_key)


__all__ = [
    "ADAPTERS",
    "LLMNotConfigured",
    "LLMRateLimited",
    "LLMResult",
    "LLMUnavailable",
    "Provider",
    "Turn",
    "get_provider",
    "provider_for",
]
