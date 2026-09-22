import warnings
from typing import Literal, Self

from pydantic import HttpUrl, model_validator
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


settings = Settings()  # type: ignore[call-arg]
