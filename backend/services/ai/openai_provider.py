from __future__ import annotations

import logging
import time
import base64

from backend.config import get_ai_api_key
from backend.services.ai.base import AIMessage, AIProvider, AIResponse, AudioSpeechResponse, AudioTranscriptionResponse

log = logging.getLogger("chatbot.ai.openai")


class OpenAIProvider(AIProvider):
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None):
        self._model = model
        self._api_key = api_key.strip() if api_key is not None else get_ai_api_key("OPENAI_API_KEY")

    @property
    def provider_name(self) -> str:
        return "openai"

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
            return self._fallback("OPENAI_API_KEY não configurada")

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self._api_key, timeout=30)
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

    def generate_multimodal_json(
        self,
        system_prompt: str,
        image_data: bytes,
        mime_type: str,
        temperatura: float = 0.0,
        max_tokens: int = 2048,
    ) -> AIResponse:
        if not self._api_key:
            return AIResponse(content="", provider=self.provider_name, model=self._model, error_reason="OPENAI_API_KEY nao configurada")
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self._api_key, timeout=60)
            data_url = f"data:{mime_type};base64,{base64.b64encode(image_data).decode('ascii')}"
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": "Extraia a comanda desta imagem conforme o contrato. Retorne apenas JSON."},
                        {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                    ]},
                ],
                temperature=temperatura,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            usage = response.usage
            return AIResponse(
                content=response.choices[0].message.content or "",
                tokens_input=usage.prompt_tokens if usage else 0,
                tokens_output=usage.completion_tokens if usage else 0,
                provider=self.provider_name,
                model=self._model,
            )
        except ImportError:
            return AIResponse(content="", provider=self.provider_name, model=self._model, error_reason="pacote 'openai' nao instalado")
        except Exception as exc:
            log.exception("Erro ao analisar imagem Print Pedido: %s", exc)
            return AIResponse(content="", provider=self.provider_name, model=self._model, error_reason=str(exc))

    def transcribe_audio(
        self,
        *,
        file_path: str,
        model: str = "gpt-4o-mini-transcribe",
        language: str | None = "pt",
    ) -> AudioTranscriptionResponse:
        if not self._api_key:
            return AudioTranscriptionResponse(
                text="",
                provider=self.provider_name,
                model=model,
                language=language or "",
                error_reason="OPENAI_API_KEY nao configurada",
            )

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self._api_key, timeout=60)
            t0 = time.monotonic()
            with open(file_path, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    language=language,
                )
            latencia = int((time.monotonic() - t0) * 1000)
            return AudioTranscriptionResponse(
                text=(getattr(response, "text", "") or "").strip(),
                provider=self.provider_name,
                model=model,
                language=language or "",
                latencia_ms=latencia,
            )
        except ImportError:
            return AudioTranscriptionResponse(
                text="",
                provider=self.provider_name,
                model=model,
                language=language or "",
                error_reason="pacote 'openai' nao instalado",
            )
        except Exception as exc:
            log.exception("Erro ao transcrever audio OpenAI: %s", exc)
            return AudioTranscriptionResponse(
                text="",
                provider=self.provider_name,
                model=model,
                language=language or "",
                error_reason=str(exc),
            )

    def synthesize_speech(
        self,
        *,
        text: str,
        model: str = "gpt-4o-mini-tts",
        voice: str = "marin",
        response_format: str = "opus",
        instructions: str | None = None,
    ) -> AudioSpeechResponse:
        mime_by_format = {
            "mp3": "audio/mpeg",
            "opus": "audio/ogg",
            "aac": "audio/aac",
            "flac": "audio/flac",
            "wav": "audio/wav",
            "pcm": "audio/pcm",
        }
        if not self._api_key:
            return AudioSpeechResponse(
                audio=b"",
                provider=self.provider_name,
                model=model,
                voice=voice,
                response_format=response_format,
                mime_type=mime_by_format.get(response_format, "application/octet-stream"),
                error_reason="OPENAI_API_KEY nao configurada",
            )

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self._api_key, timeout=60)
            t0 = time.monotonic()
            kwargs = {
                "model": model,
                "voice": voice,
                "input": text,
                "response_format": response_format,
            }
            if instructions:
                kwargs["instructions"] = instructions
            response = client.audio.speech.create(**kwargs)
            audio = getattr(response, "content", None)
            if audio is None and hasattr(response, "read"):
                audio = response.read()
            if audio is None:
                audio = bytes(response)
            latencia = int((time.monotonic() - t0) * 1000)
            return AudioSpeechResponse(
                audio=audio or b"",
                provider=self.provider_name,
                model=model,
                voice=voice,
                response_format=response_format,
                mime_type=mime_by_format.get(response_format, "application/octet-stream"),
                latencia_ms=latencia,
            )
        except ImportError:
            return AudioSpeechResponse(
                audio=b"",
                provider=self.provider_name,
                model=model,
                voice=voice,
                response_format=response_format,
                mime_type=mime_by_format.get(response_format, "application/octet-stream"),
                error_reason="pacote 'openai' nao instalado",
            )
        except Exception as exc:
            log.exception("Erro ao gerar audio OpenAI: %s", exc)
            return AudioSpeechResponse(
                audio=b"",
                provider=self.provider_name,
                model=model,
                voice=voice,
                response_format=response_format,
                mime_type=mime_by_format.get(response_format, "application/octet-stream"),
                error_reason=str(exc),
            )
