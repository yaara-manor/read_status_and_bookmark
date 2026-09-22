from sqlalchemy import text
from sqlmodel import Session


def test_user_and_outbox_exist(db: Session) -> None:
    tables = set(
        db.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).scalars()
    )
    assert "user" in tables
    assert "outbox" in tables
    version_rows = db.execute(
        text("SELECT count(*) FROM alembic_version_user_crud")
    ).scalar_one()
    assert version_rows == 1
