import pytest

from app.core.config import Settings


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "DATABASE_URL": "postgresql+psycopg://user:s3cret@localhost/app_test",
        "INTERNAL_API_KEY": "k",
        "FASTAPI_ENV": None,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_database_url_postgres_scheme_becomes_psycopg() -> None:
    configured = Settings(
        DATABASE_URL="postgres://user:s3cret@localhost/app_test",
        INTERNAL_API_KEY="k",
    )
    assert str(configured.DATABASE_URL).startswith("postgresql+psycopg://")


def test_internal_api_key_changethis_raises_outside_development() -> None:
    with pytest.raises(ValueError, match="INTERNAL_API_KEY"):
        _settings(INTERNAL_API_KEY="changethis")


def test_internal_api_key_changethis_warns_in_development() -> None:
    with pytest.warns(UserWarning, match="INTERNAL_API_KEY"):
        _settings(INTERNAL_API_KEY="changethis", FASTAPI_ENV="development")
