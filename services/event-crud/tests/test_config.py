from app.core.config import Settings


def test_database_url_postgres_scheme_becomes_psycopg() -> None:
    configured = Settings(
        DATABASE_URL="postgres://user:s3cret@localhost/app_test",
        INTERNAL_API_KEY="k",
    )
    assert str(configured.DATABASE_URL).startswith("postgresql+psycopg://")
