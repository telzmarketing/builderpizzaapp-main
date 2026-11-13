from __future__ import annotations

from typing import Literal

from sqlalchemy.orm import object_session

from backend.config import get_ai_api_key
from backend.models.agente_whatsapp import AgenteWhatsAppAISettings
from backend.models.chatbot import AIProviderEnum, ChatbotSettings
from backend.services.ai.base import AIMessage, AIProvider, AIResponse
from backend.services.ai.claude_provider import ClaudeProvider
from backend.services.ai.openai_provider import OpenAIProvider
from backend.services.ai.credentials import resolve_ai_credential

ProviderName = Literal["claude", "openai"]
AISettings = ChatbotSettings | AgenteWhatsAppAISettings

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


class _UnavailableProvider(AIProvider):
    """Explicitly disabled provider used by the Atendimento internal mode."""

    @property
    def provider_name(self) -> str:
        return "internal"

    def generate(
        self,
        system_prompt: str,
        messages: list[AIMessage],
        temperatura: float = 0.7,
        max_tokens: int = 1024,
    ) -> AIResponse:
        return AIResponse(content="", provider=self.provider_name, error_reason="provider_internal")


def _is_atendimento_settings(settings: AISettings) -> bool:
    return isinstance(settings, AgenteWhatsAppAISettings)


def _db_key(settings: AISettings | None, name: str) -> str:
    """Read the central tenant credential, then compatibility fallbacks."""
    if name == "ANTHROPIC_API_KEY":
        db_val = getattr(settings, "anthropic_api_key", None)
        provider = "claude"
    else:
        db_val = getattr(settings, "openai_api_key", None)
        provider = "openai"
    session = object_session(settings) if settings is not None else None
    tenant_id = getattr(settings, "tenant_id", None)
    if session is not None and tenant_id:
        return resolve_ai_credential(session, tenant_id, provider, legacy_key=db_val).api_key
    return (db_val or "").strip() or get_ai_api_key(name)


def _key_preview(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 10:
        return "configurada"
    return f"{key[:4]}...{key[-4:]}"


def get_ai_provider(settings: AISettings) -> AIProvider:
    """Resolve a provider from either legacy Chatbot or Atendimento settings.

    Print Pedido intentionally passes AgenteWhatsAppAISettings here. The
    Gestor IA has a separate settings/service path and is not included.
    """
    if _is_atendimento_settings(settings):
        provider_name = settings.provider
        if provider_name == "internal" or provider_name not in {"openai", "claude"}:
            return _UnavailableProvider()
        model = settings.model or DEFAULT_MODELS[provider_name]
        return _provider_instance(provider_name, settings, model=model)

    provider_name = _select_provider(settings)
    model = _select_model(provider_name, settings.modelo_ia)

    return _provider_instance(provider_name, settings, model=model)


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


def _provider_instance(
    provider_name: str,
    settings: AISettings | None = None,
    *,
    model: str | None = None,
) -> AIProvider:
    if provider_name == "internal":
        return _UnavailableProvider()
    if provider_name == "openai":
        key = _db_key(settings, "OPENAI_API_KEY") if settings else ""
        return OpenAIProvider(model=model or DEFAULT_MODELS["openai"], api_key=key)
    key = _db_key(settings, "ANTHROPIC_API_KEY") if settings else ""
    return ClaudeProvider(model=model or DEFAULT_MODELS["claude"], api_key=key)
