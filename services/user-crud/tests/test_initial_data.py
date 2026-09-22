import runpy
from pathlib import Path

from sqlmodel import Session, func, select

from app.core.config import settings
from app.core.db import engine, init_db
from app.initial_data import main
from app.models import Outbox, User, get_datetime_utc


def _superuser_count(session: Session) -> int:
    return session.exec(
        select(func.count())
        .select_from(User)
        .where(User.email == settings.FIRST_SUPERUSER)
    ).one()


def test_init_db_creates_superuser_and_outbox_when_missing() -> None:
    with Session(engine) as session:
        existing = session.exec(
            select(User).where(User.email == settings.FIRST_SUPERUSER)
        ).one()
        session.delete(existing)
        session.commit()
        before = session.exec(select(func.count()).select_from(Outbox)).one()

        init_db(session)

        created = session.exec(
            select(User).where(User.email == settings.FIRST_SUPERUSER)
        ).one()
        assert created.is_superuser is True
        rows = session.exec(
            select(Outbox).where(Outbox.event_name == "UserCreated")
        ).all()
        match = [row for row in rows if str(row.payload["id"]) == str(created.id)]
        assert len(match) == 1
        assert (
            session.exec(select(func.count()).select_from(Outbox)).one() == before + 1
        )
        match[0].published_at = get_datetime_utc()
        session.add(match[0])
        session.commit()


def test_init_db_returns_when_superuser_exists() -> None:
    with Session(engine) as session:
        before_users = _superuser_count(session)
        before_outbox = session.exec(select(func.count()).select_from(Outbox)).one()
        init_db(session)
        assert _superuser_count(session) == before_users == 1
        assert (
            session.exec(select(func.count()).select_from(Outbox)).one()
            == before_outbox
        )


def test_initial_data_main_logs_and_leaves_superuser() -> None:
    assert main() is None
    with Session(engine) as session:
        assert _superuser_count(session) == 1


def test_initial_data_module_main_runs() -> None:
    path = Path(main.__code__.co_filename)
    runpy.run_path(str(path), run_name="__main__")
    with Session(engine) as session:
        assert _superuser_count(session) == 1
