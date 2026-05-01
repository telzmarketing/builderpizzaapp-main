from __future__ import annotations

from typing import Literal

from backend.config import get_ai_api_key
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


def _db_key(settings: ChatbotSettings, name: str) -> str:
    """Read API key from DB settings (primary) or fall back to env."""
    if name == "ANTHROPIC_API_KEY":
        db_val = getattr(settings, "anthropic_api_key", None)
    else:
        db_val = getattr(settings, "openai_api_key", None)
    return (db_val or "").strip() or get_ai_api_key(name)


def _key_preview(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 10:
        return "configurada"
    return f"{key[:4]}...{key[-4:]}"


def get_ai_provider(settings: ChatbotSettings) -> AIProvider:
    """Return the selected AI provider, falling back to a configured provider."""
    provider_name = _select_provider(settings)
    model = _select_model(provider_name, settings.modelo_ia)

    if provider_name == "openai":
        return OpenAIProvider(model=model, api_key=_db_key(settings, "OPENAI_API_KEY"))
    return ClaudeProvider(model=model, api_key=_db_key(settings, "ANTHROPIC_API_KEY"))


def check_provider_status(settings: ChatbotSettings) -> dict[str, bool | str | None]:
    """Return provider availability and masked key previews without exposing secrets."""
    claude_key  = _db_key(settings, "ANTHROPIC_API_KEY")
    openai_key  = _db_key(settings, "OPENAI_API_KEY")
    selected_provider = _select_provider(settings)
    return {
        "claude": bool(claude_key),
        "openai": bool(openai_key),
        "ativo": bool(claude_key if selected_provider == "claude" else openai_key),
        "using_fallback_provider": selected_provider != _provider_value(settings),
        "openai_key_preview": _key_preview(openai_key),
        "anthropic_key_preview": _key_preview(claude_key),
    }


def _select_provider(settings: ChatbotSettings) -> ProviderName:
    requested = _provider_value(settings)
    if _provider_instance(requested, settings).is_configured():
        return requested

    alternate: ProviderName = "openai" if requested == "claude" else "claude"
    if _provider_instance(alternate, settings).is_configured():
        return alternate

    return requested


def _select_model(provider_name: ProviderName, requested_model: str | None) -> str:
    if requested_model in KNOWN_MODELS[provider_name]:
        return requested_model
    return DEFAULT_MODELS[provider_name]


def _provider_value(settings: ChatbotSettings) -> ProviderName:
    value = settings.provedor_ia.value if isinstance(settings.provedor_ia, AIProviderEnum) else settings.provedor_ia
    return "openai" if value == "openai" else "claude"


def _provider_instance(provider_name: ProviderName, settings: ChatbotSettings | None = None) -> AIProvider:
    if provider_name == "openai":
        key = _db_key(settings, "OPENAI_API_KEY") if settings else ""
        return OpenAIProvider(model=DEFAULT_MODELS["openai"], api_key=key)
    key = _db_key(settings, "ANTHROPIC_API_KEY") if settings else ""
    return ClaudeProvider(model=DEFAULT_MODELS["claude"], api_key=key)
