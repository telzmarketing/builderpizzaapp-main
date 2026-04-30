from __future__ import annotations

import logging
import time

from backend.config import get_ai_api_key
from backend.services.ai.base import AIMessage, AIProvider, AIResponse

log = logging.getLogger("chatbot.ai.openai")


class OpenAIProvider(AIProvider):
    def __init__(self, model: str = "gpt-4o-mini"):
        self._model = model

    @property
    def provider_name(self) -> str:
        return "openai"

    def is_configured(self) -> bool:
        return bool(get_ai_api_key("OPENAI_API_KEY"))

    def generate(
        self,
        system_prompt: str,
        messages: list[AIMessage],
        temperatura: float = 0.7,
        max_tokens: int = 1024,
    ) -> AIResponse:
        if not self.is_configured():
            return self._fallback("OPENAI_API_KEY não configurada")

        try:
            from openai import OpenAI

            client = OpenAI(api_key=get_ai_api_key("OPENAI_API_KEY"), timeout=30)
            payload = [{"role": "system", "content": system_prompt}]
            payload += [{"role": m.role, "content": m.content} for m in messages]

            t0 = time.monotonic()
            response = client.chat.completions.create(
                model=self._model,
                messages=payload,  # type: ignore[arg-type]
                temperature=temperatura,
                max_tokens=max_tokens,
            )
            latencia = int((time.monotonic() - t0) * 1000)
            usage = response.usage
            return AIResponse(
                content=response.choices[0].message.content or "",
                tokens_input=usage.prompt_tokens if usage else 0,
                tokens_output=usage.completion_tokens if usage else 0,
                latencia_ms=latencia,
                provider=self.provider_name,
                model=self._model,
            )

        except ImportError:
            return self._fallback("pacote 'openai' não instalado (pip install openai)")
        except Exception as exc:
            log.exception("Erro ao chamar OpenAI: %s", exc)
            return self._fallback(str(exc))
