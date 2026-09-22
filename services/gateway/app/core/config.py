from typing import Literal

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Two levels above ./services/gateway/
        env_file="../../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    PROJECT_NAME: str
    FRONTEND_HOST: str = "http://localhost:5173"
    USER_CRUD_URL: str
    EVENT_CRUD_URL: str
    INTERNAL_API_KEY: str
    SENTRY_DSN: HttpUrl | None = None
    FASTAPI_ENV: Literal["development"] | None = None


settings = Settings()  # type: ignore[call-arg]
