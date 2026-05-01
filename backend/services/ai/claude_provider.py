from __future__ import annotations

import logging
import time

from backend.config import get_ai_api_key
from backend.services.ai.base import AIMessage, AIProvider, AIResponse

log = logging.getLogger("chatbot.ai.claude")


class ClaudeProvider(AIProvider):
    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str = ""):
        self._model = model
        self._api_key = api_key.strip() or get_ai_api_key("ANTHROPIC_API_KEY")

    @property
    def provider_name(self) -> str:
        return "claude"

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def generate(
        self,
        system_prompt: str,
        messages: list[AIMessage],
        temperatura: float = 0.7,
        max_tokens: int = 1024,
    ) -> AIResponse:
        if not self._api_key:
            return self._fallback("ANTHROPIC_API_KEY não configurada")

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self._api_key)
            t0 = time.monotonic()
            response = client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperatura,
                system=system_prompt,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                timeout=30,
            )
            latencia = int((time.monotonic() - t0) * 1000)
            return AIResponse(
                content=response.content[0].text,
                tokens_input=response.usage.input_tokens,
                tokens_output=response.usage.output_tokens,
                latencia_ms=latencia,
                provider=self.provider_name,
                model=self._model,
            )

        except ImportError:
            return self._fallback("pacote 'anthropic' não instalado (pip install anthropic)")
        except Exception as exc:
            log.exception("Erro ao chamar Claude: %s", exc)
            return self._fallback(str(exc))
