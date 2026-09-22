import pytest

from app.core.config import Settings, settings


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "SECRET_KEY": "not-the-default-secret",
        "PROJECT_NAME": "Coverage",
        "DATABASE_URL": "postgresql+psycopg://user:s3cret@localhost/app_test",
        "INTERNAL_API_KEY": "k",
        "FIRST_SUPERUSER": "admin@example.com",
        "FIRST_SUPERUSER_PASSWORD": "not-the-default-secret",
        "FASTAPI_ENV": None,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_database_url_postgres_scheme_becomes_psycopg() -> None:
    configured = _settings(DATABASE_URL="postgresql://user:s3cret@localhost/app_test")
    assert str(configured.DATABASE_URL).startswith("postgresql+psycopg://")


def test_emails_enabled_follows_host_and_from_address() -> None:
    assert isinstance(settings.emails_enabled, bool)
    disabled = _settings(SMTP_HOST=None, EMAILS_FROM_EMAIL=None)
    assert disabled.emails_enabled is False
    enabled = _settings(SMTP_HOST="localhost", EMAILS_FROM_EMAIL="from@example.com")
    assert enabled.emails_enabled is True


def test_default_secret_raises_outside_development() -> None:
    with pytest.raises(ValueError, match="SECRET_KEY"):
        _settings(SECRET_KEY="changethis")


def test_internal_api_key_changethis_raises_outside_development() -> None:
    with pytest.raises(ValueError, match="INTERNAL_API_KEY"):
        _settings(INTERNAL_API_KEY="changethis")


def test_internal_api_key_changethis_warns_in_development() -> None:
    with pytest.warns(UserWarning, match="INTERNAL_API_KEY"):
        _settings(INTERNAL_API_KEY="changethis", FASTAPI_ENV="development")
