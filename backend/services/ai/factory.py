from __future__ import annotations

from backend.models.chatbot import AIProviderEnum, ChatbotSettings
from backend.services.ai.base import AIProvider
from backend.services.ai.claude_provider import ClaudeProvider
from backend.services.ai.openai_provider import OpenAIProvider


def get_ai_provider(settings: ChatbotSettings) -> AIProvider:
    """Fábrica: lê provedor e modelo das settings e retorna a instância correta."""
    model = settings.modelo_ia or "claude-sonnet-4-6"
    if settings.provedor_ia == AIProviderEnum.openai:
        return OpenAIProvider(model=model)
    return ClaudeProvider(model=model)


def check_provider_status(settings: ChatbotSettings) -> dict[str, bool]:
    """Retorna status (configurado/não) de cada provedor — sem expor as chaves."""
    return {
        "claude": ClaudeProvider().is_configured(),
        "openai": OpenAIProvider().is_configured(),
        "ativo":  get_ai_provider(settings).is_configured(),
    }
