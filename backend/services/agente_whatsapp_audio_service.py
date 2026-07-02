from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import PROJECT_ROOT, get_ai_api_key, get_settings
from backend.models.agente_whatsapp import (
    AgenteWhatsAppAISettings,
    AgenteWhatsAppAudioArtifact,
    AgenteWhatsAppMessage,
)
from backend.services.ai.openai_provider import OpenAIProvider
from backend.services.agente_whatsapp_audio_settings_service import AgenteWhatsAppAudioSettingsService


_AUDIO_MIME_EXTENSIONS = {
    "audio/ogg": "ogg",
    "audio/opus": "opus",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/aac": "aac",
    "audio/webm": "webm",
    "video/mp4": "mp4",
}


@dataclass
class _AudioSource:
    data: bytes
    mime_type: str
    source_url: str | None = None
    provider_payload: dict[str, Any] | None = None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _json_dump(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=str)


def _json_load(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_error(value: Any) -> str:
    text_value = str(value or "").strip()
    if not text_value:
        return "Falha desconhecida."
    return text_value.replace("\r", " ").replace("\n", " ")[:500]


class AgenteWhatsAppAudioService:
    def __init__(self, db: Session):
        self._db = db
        self._settings = get_settings()

    def transcribe_message(self, message_id: str, *, force: bool = False) -> dict[str, Any]:
        message = self._db.query(AgenteWhatsAppMessage).filter(AgenteWhatsAppMessage.id == message_id).first()
        if not message:
            raise ValueError("Mensagem do AGENTE WHATSAPP nao encontrada.")
        if message.message_type != "audio":
            raise ValueError("A mensagem informada nao e audio.")
        if message.transcription_status == "done" and message.transcription_text and not force:
            return self.serialize_audio_state(message)

        if not self._settings.WHATSAPP_AUDIO_INPUT_ENABLED:
            self._mark_failure(message, "Entrada de audio desativada por configuracao.", status="failed")
            return self.serialize_audio_state(message)

        message.transcription_status = "processing"
        message.transcription_error = None
        message.processing_status = "processing"
        self._db.flush()

        try:
            source = self._load_audio_source(message)
            self._validate_source(source)
            stored_path, public_url, storage_key = self._store_audio(source, message)
            message.media_url = message.media_url or public_url
            message.media_storage_key = storage_key
            message.media_mime_type = source.mime_type
            message.media_size_bytes = len(source.data)
            self._record_artifact(message, source, storage_key=storage_key, public_url=public_url)

            result = self._transcribe_with_fallback(stored_path)
            if result.get("error"):
                self._mark_failure(message, result["error"], status="failed")
                return self.serialize_audio_state(message)

            text_value = str(result.get("text") or "").strip()
            quality = self._quality_signals(text_value)
            quality["latencia_ms"] = int(result.get("latencia_ms") or 0)
            if not text_value:
                self._mark_failure(message, "Audio sem fala detectavel.", status="failed", quality=quality)
                return self.serialize_audio_state(message)

            transcription_status = "low_confidence" if quality["low_confidence"] else "done"
            message.transcription_status = transcription_status
            message.transcription_text = text_value
            message.transcription_language = str(result.get("language") or "pt")
            message.transcription_provider = str(result.get("provider") or "openai")
            message.transcription_model = str(result.get("model") or self._settings.WHATSAPP_AUDIO_STT_MODEL)
            message.transcription_error = None
            message.transcription_quality_json = _json_dump(quality)
            message.processing_status = "done"
            message.processed_at = _now_utc()
            if not (message.body or "").strip():
                message.body = text_value
            self._db.flush()
            return self.serialize_audio_state(message)
        except Exception as exc:
            self._mark_failure(message, _safe_error(exc), status="failed")
            return self.serialize_audio_state(message)

    def serialize_audio_state(self, message: AgenteWhatsAppMessage) -> dict[str, Any]:
        return {
            "message_id": message.id,
            "message_type": message.message_type,
            "media_url": message.media_url,
            "media_storage_key": message.media_storage_key,
            "media_mime_type": message.media_mime_type,
            "media_duration_ms": message.media_duration_ms,
            "media_size_bytes": message.media_size_bytes,
            "transcription_status": message.transcription_status,
            "transcription_text": message.transcription_text,
            "transcription_language": message.transcription_language,
            "transcription_provider": message.transcription_provider,
            "transcription_model": message.transcription_model,
            "transcription_error": message.transcription_error,
            "transcription_quality": _json_load(message.transcription_quality_json),
            "processing_status": message.processing_status,
            "processed_at": message.processed_at,
        }

    def synthesize_response_audio(
        self,
        response_message_id: str,
        *,
        source_message_id: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        response_message = (
            self._db.query(AgenteWhatsAppMessage)
            .filter(AgenteWhatsAppMessage.id == response_message_id)
            .first()
        )
        if not response_message:
            raise ValueError("Mensagem de resposta do AGENTE WHATSAPP nao encontrada.")
        if response_message.direction != "outbound" or response_message.sender_type != "ai":
            raise ValueError("A mensagem informada nao e uma resposta outbound da IA.")
        if response_message.message_type != "text":
            raise ValueError("A mensagem informada nao e uma resposta textual para TTS.")
        if not response_message.session:
            raise ValueError("Sessao da resposta textual nao encontrada para TTS.")

        existing_audio = self._existing_tts_message(response_message.id)
        if existing_audio and not force:
            return {
                "status": "existing",
                "message": self._serialize_tts_message(existing_audio),
            }

        text_value = self._prepare_tts_text(response_message.body or "")
        if not text_value:
            raise ValueError("Resposta textual vazia para gerar audio.")

        audio_settings = AgenteWhatsAppAudioSettingsService(self._db).get_settings()
        if not audio_settings["enabled"]:
            raise ValueError("Saida de audio desativada por configuracao.")

        ai_settings = self._db.query(AgenteWhatsAppAISettings).filter(AgenteWhatsAppAISettings.id == "default").first()
        api_key = ((ai_settings.openai_api_key if ai_settings else "") or get_ai_api_key("OPENAI_API_KEY")).strip()
        provider = OpenAIProvider(api_key=api_key)
        result = provider.synthesize_speech(
            text=text_value,
            model=str(audio_settings["tts_model"]),
            voice=str(audio_settings["tts_voice"]),
            response_format=str(audio_settings["tts_format"]),
            instructions="Fale em portugues brasileiro, com tom claro, natural e profissional.",
        )
        if result.error_reason or not result.audio:
            raise ValueError(result.error_reason or "TTS retornou audio vazio.")

        storage_key, public_url = self._store_generated_audio(
            result.audio,
            response_message,
            response_format=result.response_format,
        )

        from backend.services.agente_whatsapp_service import AgenteWhatsAppService

        audio_message = AgenteWhatsAppService(self._db).add_message(
            response_message.session,
            direction="outbound",
            sender_type="ai",
            message_type="audio",
            body=text_value,
            media_url=public_url,
            media_storage_key=storage_key,
            media_mime_type=result.mime_type,
            media_size_bytes=len(result.audio),
            response_to_message_id=response_message.id,
            provider_status="queued",
            raw_payload={
                "source": "agente_whatsapp_tts",
                "tts_source_message_id": response_message.id,
                "source_message_id": source_message_id,
                "text_fallback_message_id": response_message.id,
                "tts": {
                    "provider": result.provider,
                    "model": result.model,
                    "voice": result.voice,
                    "format": result.response_format,
                    "latencia_ms": result.latencia_ms,
                    "ptt": bool(audio_settings["send_as_ptt"]),
                },
                "manager_review": {
                    "reviewer": "internal_manager_rules_v1",
                    "decision": "approve",
                    "risk_level": "low",
                    "approved_for_auto_queue": True,
                    "requires_human_review": False,
                    "reasons": [],
                    "warnings": [],
                },
            },
        )
        self._record_tts_artifact(
            audio_message,
            storage_key=storage_key,
            public_url=public_url,
            mime_type=result.mime_type,
            size_bytes=len(result.audio),
            model=result.model,
            payload={
                "source_message_id": source_message_id,
                "text_response_message_id": response_message.id,
                "voice": result.voice,
                "format": result.response_format,
                "latencia_ms": result.latencia_ms,
            },
        )
        self._db.flush()
        return {
            "status": "generated",
            "message": self._serialize_tts_message(audio_message),
        }

    def _load_audio_source(self, message: AgenteWhatsAppMessage) -> _AudioSource:
        media_ref = (message.media_storage_key or message.media_url or "").strip()
        raw_payload = _json_load(message.raw_payload_json)
        if media_ref.startswith("/uploads/") or media_ref.startswith("uploads/"):
            return self._read_local_upload(media_ref)
        if media_ref.startswith("http://") or media_ref.startswith("https://"):
            return self._download_http(media_ref)
        if message.provider == "official" and media_ref:
            return self._download_meta_media(media_ref)
        baileys_media = ((raw_payload.get("message") or {}).get("raw_payload") or {}).get("message")
        if isinstance(baileys_media, dict):
            url = baileys_media.get("media_url")
            if isinstance(url, str) and url.startswith(("/uploads/", "uploads/")):
                return self._read_local_upload(url)
        raise ValueError("Midia de audio indisponivel para download.")

    def _read_local_upload(self, media_ref: str) -> _AudioSource:
        relative = media_ref.lstrip("/").replace("\\", "/")
        path = (PROJECT_ROOT / relative).resolve()
        uploads_root = (PROJECT_ROOT / "uploads").resolve()
        if uploads_root not in path.parents and path != uploads_root:
            raise ValueError("Caminho de audio local invalido.")
        if not path.exists() or not path.is_file():
            raise ValueError("Arquivo de audio local nao encontrado.")
        data = path.read_bytes()
        mime_type = self._guess_mime_from_path(path)
        return _AudioSource(data=data, mime_type=mime_type, source_url=f"/{relative}")

    def _download_http(self, url: str, *, headers: dict[str, str] | None = None) -> _AudioSource:
        import requests

        response = requests.get(url, headers=headers or {}, timeout=45)
        response.raise_for_status()
        data = response.content
        mime_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
        if not mime_type:
            mime_type = self._guess_mime_from_url(url)
        return _AudioSource(data=data, mime_type=mime_type, source_url=url)

    def _download_meta_media(self, media_id: str) -> _AudioSource:
        import requests

        creds = self._load_meta_credentials()
        token = creds.get("access_token")
        if not token:
            raise ValueError("Credencial WhatsApp Cloud ausente para baixar audio.")
        headers = {"Authorization": f"Bearer {token}"}
        info_response = requests.get(f"https://graph.facebook.com/v19.0/{media_id}", headers=headers, timeout=20)
        info_response.raise_for_status()
        media_info = info_response.json() if info_response.content else {}
        media_url = media_info.get("url")
        if not media_url:
            raise ValueError("WhatsApp Cloud nao retornou URL da midia.")
        source = self._download_http(str(media_url), headers=headers)
        source.provider_payload = {
            "media_id": media_id,
            "mime_type": media_info.get("mime_type"),
            "file_size": media_info.get("file_size"),
            "sha256": media_info.get("sha256"),
        }
        if media_info.get("mime_type"):
            source.mime_type = str(media_info["mime_type"]).split(";", 1)[0].strip().lower()
        return source

    def _load_meta_credentials(self) -> dict[str, Any]:
        conn = self._db.execute(
            text("SELECT credentials_json FROM integration_connections WHERE integration_type = 'whatsapp_cloud'")
        ).fetchone()
        if not conn or not conn[0]:
            return {}
        try:
            data = json.loads(conn[0])
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _validate_source(self, source: _AudioSource) -> None:
        if source.mime_type not in _AUDIO_MIME_EXTENSIONS:
            raise ValueError(f"Tipo de audio nao permitido: {source.mime_type or 'desconhecido'}.")
        if not source.data:
            raise ValueError("Arquivo de audio vazio.")
        if len(source.data) > int(self._settings.WHATSAPP_AUDIO_MAX_INPUT_BYTES):
            raise ValueError("Arquivo de audio excede o limite configurado.")

    def _store_audio(self, source: _AudioSource, message: AgenteWhatsAppMessage) -> tuple[Path, str, str]:
        ext = _AUDIO_MIME_EXTENSIONS.get(source.mime_type, "bin")
        storage_dir = (PROJECT_ROOT / self._settings.WHATSAPP_AUDIO_STORAGE_DIR).resolve()
        storage_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{message.id}-{uuid.uuid4().hex}.{ext}"
        path = storage_dir / filename
        path.write_bytes(source.data)
        storage_key = path.relative_to(PROJECT_ROOT).as_posix()
        return path, f"/{storage_key}", storage_key

    def _record_artifact(
        self,
        message: AgenteWhatsAppMessage,
        source: _AudioSource,
        *,
        storage_key: str,
        public_url: str,
    ) -> AgenteWhatsAppAudioArtifact:
        artifact = AgenteWhatsAppAudioArtifact(
            id=str(uuid.uuid4()),
            message_id=message.id,
            artifact_type="original",
            storage_key=storage_key,
            media_url=public_url,
            mime_type=source.mime_type,
            size_bytes=len(source.data),
            duration_ms=message.media_duration_ms,
            provider=message.provider,
            status="stored",
            payload_json=_json_dump(source.provider_payload or {"source_url": source.source_url}),
            created_at=_now_utc(),
            updated_at=_now_utc(),
        )
        self._db.add(artifact)
        self._db.flush()
        return artifact

    def _store_generated_audio(
        self,
        data: bytes,
        response_message: AgenteWhatsAppMessage,
        *,
        response_format: str,
    ) -> tuple[str, str]:
        storage_dir = (PROJECT_ROOT / self._settings.WHATSAPP_AUDIO_STORAGE_DIR).resolve()
        storage_dir.mkdir(parents=True, exist_ok=True)
        ext = self._extension_for_tts_format(response_format)
        filename = f"tts-{response_message.id}-{uuid.uuid4().hex}.{ext}"
        path = storage_dir / filename
        path.write_bytes(data)
        storage_key = path.relative_to(PROJECT_ROOT).as_posix()
        return storage_key, f"/{storage_key}"

    def _record_tts_artifact(
        self,
        message: AgenteWhatsAppMessage,
        *,
        storage_key: str,
        public_url: str,
        mime_type: str,
        size_bytes: int,
        model: str,
        payload: dict[str, Any],
    ) -> AgenteWhatsAppAudioArtifact:
        artifact = AgenteWhatsAppAudioArtifact(
            id=str(uuid.uuid4()),
            message_id=message.id,
            artifact_type="tts",
            storage_key=storage_key,
            media_url=public_url,
            mime_type=mime_type,
            size_bytes=size_bytes,
            provider="openai",
            model=model,
            status="generated",
            payload_json=_json_dump(payload),
            created_at=_now_utc(),
            updated_at=_now_utc(),
        )
        self._db.add(artifact)
        self._db.flush()
        return artifact

    def _transcribe_with_fallback(self, file_path: Path) -> dict[str, Any]:
        ai_settings = self._db.query(AgenteWhatsAppAISettings).filter(AgenteWhatsAppAISettings.id == "default").first()
        api_key = ((ai_settings.openai_api_key if ai_settings else "") or get_ai_api_key("OPENAI_API_KEY")).strip()
        provider = OpenAIProvider(api_key=api_key)
        primary_model = self._settings.WHATSAPP_AUDIO_STT_MODEL
        fallback_model = self._settings.WHATSAPP_AUDIO_STT_FALLBACK_MODEL

        primary = provider.transcribe_audio(file_path=str(file_path), model=primary_model, language="pt")
        primary_quality = self._quality_signals(primary.text)
        if not primary.error_reason and primary.text and not primary_quality["low_confidence"]:
            return {
                "text": primary.text,
                "provider": primary.provider,
                "model": primary.model,
                "language": primary.language,
                "latencia_ms": primary.latencia_ms,
            }

        if fallback_model and fallback_model != primary_model:
            fallback = provider.transcribe_audio(file_path=str(file_path), model=fallback_model, language="pt")
            fallback_quality = self._quality_signals(fallback.text)
            if not fallback.error_reason and fallback.text:
                return {
                    "text": fallback.text,
                    "provider": fallback.provider,
                    "model": fallback.model,
                    "language": fallback.language,
                    "latencia_ms": fallback.latencia_ms,
                    "low_confidence": fallback_quality["low_confidence"],
                }

        return {
            "text": primary.text,
            "provider": primary.provider,
            "model": primary.model,
            "language": primary.language,
            "latencia_ms": primary.latencia_ms,
            "error": primary.error_reason,
            "low_confidence": primary_quality["low_confidence"],
        }

    def _quality_signals(self, text_value: str | None) -> dict[str, Any]:
        cleaned = (text_value or "").strip()
        words = [item for item in cleaned.split() if item.strip()]
        repeated_chars = any(char * 5 in cleaned.lower() for char in "abcdefghijklmnopqrstuvwxyz")
        low_confidence = not cleaned or len(cleaned) < 4 or len(words) < 1 or repeated_chars
        return {
            "low_confidence": low_confidence,
            "text_length": len(cleaned),
            "word_count": len(words),
            "repeated_chars": repeated_chars,
        }

    def _mark_failure(
        self,
        message: AgenteWhatsAppMessage,
        error: str,
        *,
        status: str,
        quality: dict[str, Any] | None = None,
    ) -> None:
        now = _now_utc()
        message.transcription_status = status
        message.transcription_error = _safe_error(error)
        message.transcription_quality_json = _json_dump(quality or {})
        message.processing_status = "failed"
        message.processed_at = now
        self._db.flush()

    def _existing_tts_message(self, response_message_id: str) -> AgenteWhatsAppMessage | None:
        return (
            self._db.query(AgenteWhatsAppMessage)
            .filter(
                AgenteWhatsAppMessage.direction == "outbound",
                AgenteWhatsAppMessage.message_type == "audio",
                AgenteWhatsAppMessage.response_to_message_id == response_message_id,
            )
            .order_by(AgenteWhatsAppMessage.created_at.asc())
            .first()
        )

    def _serialize_tts_message(self, message: AgenteWhatsAppMessage) -> dict[str, Any]:
        return {
            "id": message.id,
            "session_id": message.session_id,
            "message_type": message.message_type,
            "media_url": message.media_url,
            "media_storage_key": message.media_storage_key,
            "media_mime_type": message.media_mime_type,
            "media_size_bytes": message.media_size_bytes,
            "provider_status": message.provider_status,
            "response_to_message_id": message.response_to_message_id,
        }

    def _prepare_tts_text(self, text_value: str) -> str:
        cleaned = " ".join((text_value or "").split())
        audio_settings = AgenteWhatsAppAudioSettingsService(self._db).get_settings()
        max_chars = max(120, int(audio_settings["max_chars"] or 900))
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[: max_chars - 3].rstrip() + "..."

    def _extension_for_tts_format(self, response_format: str) -> str:
        value = (response_format or "").strip().lower()
        if value in {"mp3", "opus", "aac", "flac", "wav", "pcm"}:
            return value
        return "bin"

    def _guess_mime_from_path(self, path: Path) -> str:
        suffix = path.suffix.lower().lstrip(".")
        for mime_type, ext in _AUDIO_MIME_EXTENSIONS.items():
            if suffix == ext:
                return mime_type
        return "application/octet-stream"

    def _guess_mime_from_url(self, url: str) -> str:
        suffix = url.split("?", 1)[0].rsplit(".", 1)[-1].lower() if "." in url else ""
        for mime_type, ext in _AUDIO_MIME_EXTENSIONS.items():
            if suffix == ext:
                return mime_type
        return "application/octet-stream"
