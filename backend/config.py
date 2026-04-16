from pydantic_settings import BaseSettings
from functools import lru_cache


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
    PAYMENT_SECRET_KEY: str = "secret"
    PAYMENT_WEBHOOK_SECRET: str = "webhook_secret"

    # Admin JWT
    JWT_SECRET_KEY: str = "troque-esta-chave-secreta-em-producao"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480          # 8 horas

    # Loyalty
    POINTS_PER_REAL: float = 1.0           # pontos por R$ gasto
    DELIVERY_POINTS: int = 10              # bônus por pedido entregue

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"    # ignore Node/Vite env vars present in the root .env


@lru_cache()
def get_settings() -> Settings:
    return Settings()
