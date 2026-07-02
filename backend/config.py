from functools import lru_cache
import os
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/minhaloja"

    # App
    APP_NAME: str = "PizzaApp API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    PUBLIC_STORE_URL: str = ""
    VITE_PUBLIC_STORE_URL: str = ""

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"dev", "development"}:
                return True
        return value

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"]

    # Payments (placeholders — swap for real gateway keys)
    PAYMENT_GATEWAY: str = "mock"          # "mock" | "stripe" | "mercadopago"
    PAYMENT_PROVIDER: str = "mock"         # "mock" | "mercado_pago" | "mercadopago"
    PAYMENT_SECRET_KEY: str = "secret"
    PAYMENT_WEBHOOK_SECRET: str = "webhook_secret"
    MERCADO_PAGO_ACCESS_TOKEN: str = ""
    MERCADO_PAGO_PUBLIC_KEY: str = ""
    MERCADO_PAGO_WEBHOOK_SECRET: str = ""

    # Admin JWT
    JWT_SECRET_KEY: str = "troque-esta-chave-secreta-em-producao"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480          # 8 horas

    # Loyalty
    POINTS_PER_REAL: float = 1.0           # pontos por R$ gasto
    DELIVERY_POINTS: int = 10              # bônus por pedido entregue

    # Chatbot — AI providers (nunca expostos ao frontend)
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # AGENTE WHATSAPP - outbox worker
    AGENTE_WHATSAPP_WORKER_ENABLED: bool = True
    AGENTE_WHATSAPP_WORKER_INTERVAL_SECONDS: int = 10
    AGENTE_WHATSAPP_WORKER_BATCH_SIZE: int = 20
    AGENTE_WHATSAPP_PROVIDER_FAILURE_THRESHOLD: int = 5
    AGENTE_WHATSAPP_PROVIDER_PAUSE_MINUTES: int = 30
    AGENTE_WHATSAPP_DEAD_ALERT_AFTER_MINUTES: int = 5
    WHATSAPP_AUDIO_INPUT_ENABLED: bool = True
    WHATSAPP_AUDIO_TRANSCRIPTION_WORKER_ENABLED: bool = True
    WHATSAPP_AUDIO_MAX_INPUT_BYTES: int = 20 * 1024 * 1024
    WHATSAPP_AUDIO_STT_MODEL: str = "gpt-4o-mini-transcribe"
    WHATSAPP_AUDIO_STT_FALLBACK_MODEL: str = "gpt-4o-transcribe"
    WHATSAPP_AUDIO_STORAGE_DIR: str = "uploads/agente-whatsapp-audio"
    WHATSAPP_CAMPAIGN_CONTEXT_ENABLED: bool = True
    WHATSAPP_CAMPAIGN_CONTEXT_WINDOW_HOURS: int = 72
    WHATSAPP_CAMPAIGN_PRIORITY_WINDOW_HOURS: int = 24
    WHATSAPP_AI_AUTO_REPLY_ENABLED: bool = False
    WHATSAPP_AUDIO_OUTPUT_ENABLED: bool = False
    WHATSAPP_AUDIO_TTS_WORKER_ENABLED: bool = True
    WHATSAPP_AUDIO_TEXT_FALLBACK_ENABLED: bool = True
    WHATSAPP_AUDIO_LOW_CONFIDENCE_HANDOFF_ENABLED: bool = True
    WHATSAPP_AUDIO_RETENTION_CLEANUP_ENABLED: bool = False
    WHATSAPP_AUDIO_RETENTION_DAYS: int = 30
    WHATSAPP_AUDIO_RETENTION_BATCH_SIZE: int = 50
    WHATSAPP_GATEWAY_AUDIO_BAILEYS_ENABLED: bool = True
    WHATSAPP_AUDIO_ROLLOUT_MODE: str = "all"  # all | pilot | off
    WHATSAPP_AUDIO_ROLLOUT_PILOT_PHONES: str = ""
    WHATSAPP_AUDIO_ROLLOUT_HOURS: str = ""  # exemplo: 18:00-23:00,10:00-14:00
    WHATSAPP_AUDIO_ROLLOUT_DAILY_INPUT_LIMIT: int = 0
    WHATSAPP_AUDIO_ROLLOUT_DAILY_REPLY_LIMIT: int = 0
    WHATSAPP_AUDIO_ROLLOUT_DAILY_TTS_LIMIT: int = 0
    WHATSAPP_AUDIO_RESPONSE_MODE: str = "mirror_customer_audio"  # never | mirror_customer_audio | always | manual_only
    WHATSAPP_AUDIO_TTS_MODEL: str = "gpt-4o-mini-tts"
    WHATSAPP_AUDIO_TTS_VOICE: str = "marin"
    WHATSAPP_AUDIO_TTS_FORMAT: str = "opus"
    WHATSAPP_AUDIO_TTS_MAX_CHARS: int = 900
    WHATSAPP_AUDIO_TTS_SEND_AS_PTT: bool = True

    # WhatsApp Gateway - Baileys runtime local (nao expor publicamente)
    WHATSAPP_GATEWAY_RUNTIME_URL: str = "http://127.0.0.1:3020"
    WHATSAPP_GATEWAY_RUNTIME_TOKEN: str = ""
    WHATSAPP_GATEWAY_RUNTIME_TIMEOUT_SECONDS: int = 8
    WHATSAPP_GATEWAY_BACKEND_EVENT_URL: str = "http://127.0.0.1:8000/api/whatsapp-gateway/runtime/events"
    WHATSAPP_GATEWAY_EVENT_TOKEN: str = ""

    class Config:
        env_file = (
            PROJECT_ROOT / ".env",
            BACKEND_DIR / ".env",
        )
        env_file_encoding = "utf-8"
        extra = "ignore"    # ignore Node/Vite env vars present in the root .env


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def get_ai_api_key(name: str) -> str:
    if name not in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY"}:
        raise ValueError("Chave de IA inválida.")

    env_file_value = _read_backend_env_value(name)
    if env_file_value:
        return env_file_value

    env_value = os.environ.get(name, "").strip()
    if env_value:
        return env_value

    return getattr(get_settings(), name, "").strip()


def get_ai_api_key_preview(name: str) -> str | None:
    value = get_ai_api_key(name)
    if not value:
        return None
    if len(value) <= 10:
        return "configurada"
    return f"{value[:3]}...{value[-4:]}"


def save_ai_api_keys(*, openai_api_key: str | None = None, anthropic_api_key: str | None = None) -> None:
    updates = {
        "OPENAI_API_KEY": openai_api_key,
        "ANTHROPIC_API_KEY": anthropic_api_key,
    }
    cleaned = {
        key: value.strip()
        for key, value in updates.items()
        if value is not None and value.strip()
    }
    if not cleaned:
        return

    for key, value in cleaned.items():
        if "\n" in value or "\r" in value:
            raise ValueError(f"{key} não pode conter quebra de linha.")

    env_path = BACKEND_DIR / ".env"
    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    seen: set[str] = set()
    next_lines: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            next_lines.append(line)
            continue

        key = line.split("=", 1)[0].strip()
        if key in cleaned:
            next_lines.append(f"{key}={cleaned[key]}")
            seen.add(key)
        else:
            next_lines.append(line)

    for key, value in cleaned.items():
        if key not in seen:
            next_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")

    for key, value in cleaned.items():
        os.environ[key] = value
    get_settings.cache_clear()


def _read_backend_env_value(name: str) -> str:
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        return ""

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() != name:
            continue
        return value.strip().strip('"').strip("'")
    return ""
