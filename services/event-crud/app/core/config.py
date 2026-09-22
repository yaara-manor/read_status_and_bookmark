import warnings
from typing import Literal, Self

from pydantic import HttpUrl, PostgresDsn, field_validator, model_validator
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

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.FASTAPI_ENV == "development":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("INTERNAL_API_KEY", self.INTERNAL_API_KEY)
        return self


settings = Settings()  # type: ignore # ty: ignore[unused-ignore-comment]
