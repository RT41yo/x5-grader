# backend/app/config.py
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # === Database ===
    pg_user: str = "x5"
    pg_password: str = "x5pass"
    pg_host: str = "postgres"
    pg_port: int = 5432
    pg_db: str = "x5checker"

    # === Flask / Security ===
    secret_key: str = "super-secret"  # в проде ОБЯЗАТЕЛЬНО переопределить в .env
    # cors_origins: str | None = None  # при желании добавить белый список доменов

    # === Langflow ===
    langflow_url: str = "http://langflow:7860"
    # Необязательные — если хотите управлять через Settings, а не напрямую из env:
    flow_id_evaluate: str | None = None
    flow_id_explain: str | None = None

    # === Misc ===
    # сюда можно добавить любые флаги/таймауты если нужно

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db}"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"  # игнорировать лишние переменные окружения


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Кэшируем настройки — конструируем ровно один раз за процесс.
    """
    return Settings()
