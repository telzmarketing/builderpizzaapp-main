from functools import lru_cache
import os
from pathlib import Path

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
        raise ValueError("Chave de IA invÃ¡lida.")

    env_file_value = _read_backend_env_value(name)
    if env_file_value:
        return env_file_value

    env_value = os.environ.get(name, "").strip()
    if env_value:
        return env_value

    return getattr(get_settings(), name, "").strip()


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
            raise ValueError(f"{key} nÃ£o pode conter quebra de linha.")

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
