from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import get_settings


AUDIO_SETTINGS_KEY = "agente_whatsapp_audio"


class AgenteWhatsAppAudioSettingsService:
    def __init__(self, db: Session):
        self._db = db
        self._env = get_settings()

    def defaults(self) -> dict[str, Any]:
        return {
            "enabled": bool(self._env.WHATSAPP_AUDIO_OUTPUT_ENABLED),
            "response_mode": str(self._env.WHATSAPP_AUDIO_RESPONSE_MODE or "mirror_customer_audio"),
            "tts_model": str(self._env.WHATSAPP_AUDIO_TTS_MODEL or "gpt-4o-mini-tts"),
            "tts_voice": str(self._env.WHATSAPP_AUDIO_TTS_VOICE or "marin"),
            "tts_format": str(self._env.WHATSAPP_AUDIO_TTS_FORMAT or "opus"),
            "max_chars": int(self._env.WHATSAPP_AUDIO_TTS_MAX_CHARS or 900),
            "send_as_ptt": bool(self._env.WHATSAPP_AUDIO_TTS_SEND_AS_PTT),
        }

    def get_settings(self) -> dict[str, Any]:
        content, updated_at = self._load_site_config()
        stored = content.get(AUDIO_SETTINGS_KEY)
        data = self.defaults()
        if isinstance(stored, dict):
            data.update({key: value for key, value in stored.items() if key in data})
        return self._normalize(data, updated_at=updated_at)

    def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        content, _ = self._load_site_config()
        current = self.get_settings()
        current.update(payload)
        normalized = self._normalize(current)
        stored = {key: value for key, value in normalized.items() if key != "updated_at"}
        content[AUDIO_SETTINGS_KEY] = stored
        self._db.execute(
            text(
                "INSERT INTO site_config (id, content, updated_at) VALUES ('default', :content, NOW()) "
                "ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()"
            ),
            {"content": json.dumps(content, ensure_ascii=False, default=str)},
        )
        self._db.flush()
        return self.get_settings()

    def _load_site_config(self) -> tuple[dict[str, Any], datetime | None]:
        row = self._db.execute(text("SELECT content, updated_at FROM site_config WHERE id = 'default'")).fetchone()
        if not row:
            return {}, None
        try:
            data = json.loads(row[0] or "{}")
        except json.JSONDecodeError:
            data = {}
        return data if isinstance(data, dict) else {}, row[1]

    def _normalize(self, data: dict[str, Any], *, updated_at: datetime | None = None) -> dict[str, Any]:
        response_mode = str(data.get("response_mode") or "mirror_customer_audio").strip().lower()
        if response_mode not in {"never", "mirror_customer_audio", "always", "manual_only"}:
            response_mode = "mirror_customer_audio"
        tts_format = str(data.get("tts_format") or "opus").strip().lower()
        if tts_format not in {"mp3", "opus", "aac", "flac", "wav", "pcm"}:
            tts_format = "opus"
        max_chars = int(data.get("max_chars") or 900)
        max_chars = max(120, min(max_chars, 2000))
        return {
            "enabled": bool(data.get("enabled")),
            "response_mode": response_mode,
            "tts_model": str(data.get("tts_model") or "gpt-4o-mini-tts").strip(),
            "tts_voice": str(data.get("tts_voice") or "marin").strip(),
            "tts_format": tts_format,
            "max_chars": max_chars,
            "send_as_ptt": bool(data.get("send_as_ptt", True)),
            "updated_at": updated_at,
        }
