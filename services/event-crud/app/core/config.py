from typing import Literal

from pydantic import HttpUrl, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (two levels above ./services/event-crud/)
        env_file="../../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    DATABASE_URL: PostgresDsn
    REDIS_URL: str = "redis://localhost:6379/0"
    INTERNAL_API_KEY: str
    SENTRY_DSN: HttpUrl | None = None
    FASTAPI_ENV: Literal["development"] | None = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _use_psycopg_driver(cls, value: str | PostgresDsn) -> str:
        database_url = str(value)
        for scheme in ("postgres://", "postgresql://"):
            if database_url.startswith(scheme):
                return database_url.replace(scheme, "postgresql+psycopg://", 1)
        return database_url


settings = Settings()  # type: ignore # ty: ignore[unused-ignore-comment]
