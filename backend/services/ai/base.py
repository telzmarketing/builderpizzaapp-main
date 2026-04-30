from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AIMessage:
    role: str       # "user" | "assistant"
    content: str


@dataclass
class AIResponse:
    content: str
    tokens_input: int  = 0
    tokens_output: int = 0
    latencia_ms: int   = 0
    provider: str      = ""
    model: str         = ""
    error_reason: str  = ""


_FALLBACK = (
    "Desculpe, estou com dificuldades técnicas no momento. "
    "Por favor, entre em contato pelo WhatsApp ou tente novamente em instantes."
)


class AIProvider(ABC):
    """Interface comum para todos os provedores de IA."""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        messages: list[AIMessage],
        temperatura: float = 0.7,
        max_tokens: int = 1024,
    ) -> AIResponse: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    def is_configured(self) -> bool:
        return False

    def _fallback(self, reason: str = "") -> AIResponse:
        import logging
        if reason:
            logging.getLogger("chatbot.ai").warning("AI fallback: %s", reason)
        return AIResponse(content=_FALLBACK, provider=self.provider_name, error_reason=reason)
