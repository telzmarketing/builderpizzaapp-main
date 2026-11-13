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


@dataclass
class AudioTranscriptionResponse:
    text: str
    provider: str
    model: str
    language: str = ""
    latencia_ms: int = 0
    error_reason: str = ""


@dataclass
class AudioSpeechResponse:
    audio: bytes
    provider: str
    model: str
    voice: str
    response_format: str
    mime_type: str
    latencia_ms: int = 0
    error_reason: str = ""


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

    def generate_multimodal_json(
        self,
        system_prompt: str,
        image_data: bytes,
        mime_type: str,
        temperatura: float = 0.0,
        max_tokens: int = 2048,
    ) -> AIResponse:
        """Optional vision contract; providers without vision fail closed."""
        return AIResponse(content="", provider=self.provider_name, error_reason="multimodal_not_supported")

    def _fallback(self, reason: str = "") -> AIResponse:
        import logging
        if reason:
            logging.getLogger("chatbot.ai").warning("AI fallback: %s", reason)
        return AIResponse(content=_FALLBACK, provider=self.provider_name, error_reason=reason)
