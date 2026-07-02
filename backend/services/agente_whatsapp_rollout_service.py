from __future__ import annotations

import json
from datetime import datetime, time
from typing import Any

from sqlalchemy import text
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.local_time import local_now, local_period_bounds, local_today
from backend.models.agente_whatsapp import AgenteWhatsAppMessage
from backend.services.customer_identity_service import normalize_phone


ROLLOUT_SETTINGS_KEY = "agente_whatsapp_audio_rollout"


class AgenteWhatsAppRolloutService:
    def __init__(self, db: Session):
        self._db = db
        self._env = get_settings()
        self._settings_cache: dict[str, Any] | None = None

    def defaults(self) -> dict[str, Any]:
        return {
            "mode": str(self._env.WHATSAPP_AUDIO_ROLLOUT_MODE or "all"),
            "pilot_phones": str(self._env.WHATSAPP_AUDIO_ROLLOUT_PILOT_PHONES or ""),
            "hours": str(self._env.WHATSAPP_AUDIO_ROLLOUT_HOURS or ""),
            "daily_input_limit": int(self._env.WHATSAPP_AUDIO_ROLLOUT_DAILY_INPUT_LIMIT or 0),
            "daily_reply_limit": int(self._env.WHATSAPP_AUDIO_ROLLOUT_DAILY_REPLY_LIMIT or 0),
            "daily_tts_limit": int(self._env.WHATSAPP_AUDIO_ROLLOUT_DAILY_TTS_LIMIT or 0),
        }

    def get_settings(self) -> dict[str, Any]:
        content, updated_at = self._load_site_config()
        stored = content.get(ROLLOUT_SETTINGS_KEY)
        data = self.defaults()
        if isinstance(stored, dict):
            data.update({key: value for key, value in stored.items() if key in data})
        normalized = self._normalize(data, updated_at=updated_at)
        normalized["daily_usage"] = {
            "audio_input": self._daily_count("audio_input"),
            "ai_auto_reply": self._daily_count("ai_auto_reply"),
            "audio_output": self._daily_count("audio_output"),
        }
        return normalized

    def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        content, _ = self._load_site_config()
        current = self.get_settings()
        current.update(payload)
        normalized = self._normalize(current)
        content[ROLLOUT_SETTINGS_KEY] = {
            "mode": normalized["mode"],
            "pilot_phones": normalized["pilot_phones"],
            "hours": normalized["hours"],
            "daily_input_limit": normalized["daily_input_limit"],
            "daily_reply_limit": normalized["daily_reply_limit"],
            "daily_tts_limit": normalized["daily_tts_limit"],
        }
        self._db.execute(
            text(
                "INSERT INTO site_config (id, content, updated_at) VALUES ('default', :content, NOW()) "
                "ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()"
            ),
            {"content": json.dumps(content, ensure_ascii=False, default=str)},
        )
        self._db.flush()
        self._settings_cache = None
        return self.get_settings()

    def check_message(self, message: AgenteWhatsAppMessage, action: str) -> tuple[bool, str | None]:
        mode = self._mode()
        if mode == "off":
            return False, "Rollout de audio esta desligado por configuracao."

        phone = normalize_phone(message.session.phone if message.session else "")
        if mode == "pilot" and phone not in self._pilot_phones():
            return False, "Telefone fora do piloto de audio."

        if not self._inside_allowed_hours():
            return False, "Fora da janela horaria do rollout de audio."

        limit = self._daily_limit(action)
        if limit > 0 and self._daily_count(action) >= limit:
            return False, f"Limite diario do rollout de audio atingido para {action}."

        return True, None

    def status(self) -> dict[str, Any]:
        settings = self._rollout_settings()
        return {
            "mode": settings["mode"],
            "pilot_phones_count": len(self._pilot_phones()),
            "hours": settings["hours"],
            "daily_limits": {
                "audio_input": settings["daily_input_limit"],
                "ai_auto_reply": settings["daily_reply_limit"],
                "audio_output": settings["daily_tts_limit"],
            },
            "daily_usage": {
                "audio_input": self._daily_count("audio_input"),
                "ai_auto_reply": self._daily_count("ai_auto_reply"),
                "audio_output": self._daily_count("audio_output"),
            },
        }

    def _mode(self) -> str:
        return str(self._rollout_settings()["mode"])

    def _pilot_phones(self) -> set[str]:
        phones: set[str] = set()
        for item in str(self._rollout_settings()["pilot_phones"] or "").replace(";", ",").split(","):
            normalized = normalize_phone(item)
            if normalized:
                phones.add(normalized)
        return phones

    def _inside_allowed_hours(self) -> bool:
        ranges = self._hour_ranges()
        if not ranges:
            return True
        current = local_now().time()
        for start, end in ranges:
            if start <= end:
                if start <= current <= end:
                    return True
            elif current >= start or current <= end:
                return True
        return False

    def _hour_ranges(self) -> list[tuple[time, time]]:
        result: list[tuple[time, time]] = []
        raw = str(self._rollout_settings()["hours"] or "").strip()
        if not raw:
            return result
        for item in raw.replace(";", ",").split(","):
            if "-" not in item:
                continue
            start_raw, end_raw = [part.strip() for part in item.split("-", 1)]
            start = self._parse_time(start_raw)
            end = self._parse_time(end_raw)
            if start and end:
                result.append((start, end))
        return result

    def _parse_time(self, value: str) -> time | None:
        parts = value.split(":")
        if len(parts) != 2:
            return None
        try:
            hour = max(0, min(int(parts[0]), 23))
            minute = max(0, min(int(parts[1]), 59))
        except ValueError:
            return None
        return time(hour=hour, minute=minute)

    def _daily_limit(self, action: str) -> int:
        settings = self._rollout_settings()
        if action == "audio_input":
            return max(0, int(settings["daily_input_limit"] or 0))
        if action == "ai_auto_reply":
            return max(0, int(settings["daily_reply_limit"] or 0))
        if action == "audio_output":
            return max(0, int(settings["daily_tts_limit"] or 0))
        return 0

    def _daily_count(self, action: str) -> int:
        start_dt, end_dt = local_period_bounds(local_today(), local_today())
        query = self._db.query(func.count(AgenteWhatsAppMessage.id)).filter(
            AgenteWhatsAppMessage.created_at >= start_dt,
            AgenteWhatsAppMessage.created_at <= end_dt,
        )
        if action == "audio_input":
            query = query.filter(
                AgenteWhatsAppMessage.direction == "inbound",
                AgenteWhatsAppMessage.message_type == "audio",
            )
        elif action == "ai_auto_reply":
            query = query.filter(
                AgenteWhatsAppMessage.direction == "outbound",
                AgenteWhatsAppMessage.sender_type == "ai",
                AgenteWhatsAppMessage.response_to_message_id.isnot(None),
            )
        elif action == "audio_output":
            query = query.filter(
                AgenteWhatsAppMessage.direction == "outbound",
                AgenteWhatsAppMessage.message_type == "audio",
            )
        else:
            return 0
        return int(query.scalar() or 0)

    def _rollout_settings(self) -> dict[str, Any]:
        if self._settings_cache is None:
            content, _ = self._load_site_config()
            stored = content.get(ROLLOUT_SETTINGS_KEY)
            data = self.defaults()
            if isinstance(stored, dict):
                data.update({key: value for key, value in stored.items() if key in data})
            self._settings_cache = self._normalize(data)
        return self._settings_cache

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
        mode = str(data.get("mode") or "all").strip().lower()
        if mode not in {"all", "pilot", "off"}:
            mode = "all"
        pilot_phones = str(data.get("pilot_phones") or "").strip()
        hours = str(data.get("hours") or "").strip()
        return {
            "mode": mode,
            "pilot_phones": pilot_phones,
            "pilot_phones_count": len({
                normalize_phone(item)
                for item in pilot_phones.replace(";", ",").split(",")
                if normalize_phone(item)
            }),
            "hours": hours,
            "daily_input_limit": self._safe_limit(data.get("daily_input_limit")),
            "daily_reply_limit": self._safe_limit(data.get("daily_reply_limit")),
            "daily_tts_limit": self._safe_limit(data.get("daily_tts_limit")),
            "updated_at": updated_at,
        }

    def _safe_limit(self, value: Any) -> int:
        try:
            return max(0, min(int(value or 0), 10000))
        except (TypeError, ValueError):
            return 0
