from sqlalchemy import text
from sqlmodel import Session

_INDEXES = ("ix_venue_lower_name", "ix_performer_lower_name")


def test_lower_name_indexes_exist(db: Session) -> None:
    rows = db.execute(
        text(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE indexname IN ('ix_venue_lower_name', 'ix_performer_lower_name')"
        )
    ).all()
    found = {row.indexname: row.indexdef for row in rows}
    assert set(found) == set(_INDEXES)
    for name in _INDEXES:
        definition = found[name]
        assert "lower((name)::text)" in definition
        assert "text_pattern_ops" in definition
