import os
import re
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

_TEST_DB = "app_test"
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_BACKEND_DIR = Path(__file__).resolve().parents[1]


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _expand(value: str, file_env: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return file_env.get(key) or os.environ.get(key) or match.group(0)

    return re.sub(r"\$\{([^}]+)\}", repl, value)


def _database_url() -> str:
    file_env = _parse_env_file(_ENV_FILE)
    raw = os.environ.get("DATABASE_URL") or file_env.get("DATABASE_URL")
    if not raw:
        raise RuntimeError("DATABASE_URL is not set")
    return _expand(raw, file_env)


def _use_test_database() -> None:
    url = make_url(_database_url())
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    if url.database != _TEST_DB:
        admin = create_engine(url, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": _TEST_DB},
            ).scalar()
            if not exists:
                conn.execute(text(f"CREATE DATABASE {_TEST_DB}"))
        admin.dispose()
        url = url.set(database=_TEST_DB)
    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)


_use_test_database()

# App binds DATABASE_URL at import; these must run after the rewrite above.
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, delete  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Event, Performer, User, Venue  # noqa: E402
from tests.utils.user import authentication_token_from_email  # noqa: E402
from tests.utils.utils import get_superuser_token_headers  # noqa: E402


def _upgrade_test_db() -> None:
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "app" / "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    _upgrade_test_db()
    with Session(engine) as session:
        init_db(session)
        yield session
        session.execute(delete(Event))
        session.execute(delete(Venue))
        session.execute(delete(Performer))
        session.execute(delete(User))
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
