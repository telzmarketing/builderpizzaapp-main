from functools import lru_cache
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
