from __future__ import annotations

from typing import Literal

from backend.models.chatbot import AIProviderEnum, ChatbotSettings
from backend.services.ai.base import AIProvider
from backend.services.ai.claude_provider import ClaudeProvider
from backend.services.ai.openai_provider import OpenAIProvider

ProviderName = Literal["claude", "openai"]

DEFAULT_MODELS: dict[ProviderName, str] = {
    "claude": "claude-sonnet-4-20250514",
    "openai": "gpt-4o-mini",
}

KNOWN_MODELS: dict[ProviderName, set[str]] = {
    "claude": {
        "claude-sonnet-4-20250514",
        "claude-opus-4-1-20250805",
        "claude-opus-4-20250514",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-haiku-20241022",
    },
    "openai": {"gpt-4o-mini", "gpt-4o", "gpt-4-turbo"},
}


def get_ai_provider(settings: ChatbotSettings) -> AIProvider:
    """Return the selected AI provider, falling back to a configured provider."""
    provider_name = _select_provider(settings)
    model = _select_model(provider_name, settings.modelo_ia)

    if provider_name == "openai":
        return OpenAIProvider(model=model)
    return ClaudeProvider(model=model)


def check_provider_status(settings: ChatbotSettings) -> dict[str, bool]:
    """Return provider availability without exposing API keys."""
    selected_provider = _select_provider(settings)
    return {
        "claude": ClaudeProvider().is_configured(),
        "openai": OpenAIProvider().is_configured(),
        "ativo": get_ai_provider(settings).is_configured(),
        "using_fallback_provider": selected_provider != _provider_value(settings),
    }


def _select_provider(settings: ChatbotSettings) -> ProviderName:
    requested = _provider_value(settings)
    if _provider_instance(requested).is_configured():
        return requested

    alternate: ProviderName = "openai" if requested == "claude" else "claude"
    if _provider_instance(alternate).is_configured():
        return alternate

    return requested


def _select_model(provider_name: ProviderName, requested_model: str | None) -> str:
    if requested_model in KNOWN_MODELS[provider_name]:
        return requested_model
    return DEFAULT_MODELS[provider_name]


def _provider_value(settings: ChatbotSettings) -> ProviderName:
    value = settings.provedor_ia.value if isinstance(settings.provedor_ia, AIProviderEnum) else settings.provedor_ia
    return "openai" if value == "openai" else "claude"


def _provider_instance(provider_name: ProviderName) -> AIProvider:
    if provider_name == "openai":
        return OpenAIProvider(model=DEFAULT_MODELS["openai"])
    return ClaudeProvider(model=DEFAULT_MODELS["claude"])
