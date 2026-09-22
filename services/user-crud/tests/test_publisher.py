import uuid

import pytest
from contracts import STREAM, UserDeleted, UserMessage, dump_message
from redis import Redis
from redis.exceptions import RedisError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.models import Outbox
from app.outbox import write_outbox
from app.publisher import publish_pending, run_publisher


def test_publish_pending_publishes_one_user_deleted_then_none() -> None:
    client = Redis.from_url(settings.REDIS_URL)
    with Session(engine) as session:
        already_pending = set(
            session.exec(select(Outbox.id).where(Outbox.published_at.is_(None))).all()
        )
    publish_pending(client)
    with Session(engine) as session:
        still_pending = {
            row_id
            for row_id in already_pending
            if (row := session.get(Outbox, row_id)) is not None
            and row.published_at is None
        }

    user_id = uuid.uuid4()
    message = UserMessage(
        event_name="UserDeleted",
        payload=UserDeleted(id=user_id),
    )
    with Session(engine) as session:
        write_outbox(session, message)
        row = next(obj for obj in session.new if isinstance(obj, Outbox))
        row_id = row.id
        session.commit()

    assert publish_pending(client) == 1

    with Session(engine) as session:
        stored = session.get(Outbox, row_id)
        assert stored is not None
        assert stored.published_at is not None
        for other_id in still_pending:
            other = session.get(Outbox, other_id)
            assert other is not None
            assert other.published_at is None

    payload = dump_message(message)
    entries = client.xrange(STREAM)
    assert any(fields.get(b"data") == payload.encode() for _, fields in entries)

    assert publish_pending(client) == 0


def test_publish_pending_skips_invalid_row_and_publishes_the_next() -> None:
    bad_id = uuid.uuid4()
    user_id = uuid.uuid4()
    message = UserMessage(
        event_name="UserDeleted",
        payload=UserDeleted(id=user_id),
    )
    with Session(engine) as session:
        session.add(Outbox(id=bad_id, event_name="UserDeleted", payload={}))
        session.commit()
        write_outbox(session, message)
        good_id = next(obj for obj in session.new if isinstance(obj, Outbox)).id
        session.commit()

    client = Redis.from_url(settings.REDIS_URL)
    publish_pending(client)

    with Session(engine) as session:
        bad = session.get(Outbox, bad_id)
        good = session.get(Outbox, good_id)
        assert bad is not None and bad.published_at is None
        assert good is not None and good.published_at is not None
    payload = dump_message(message)
    assert any(
        fields.get(b"data") == payload.encode() for _, fields in client.xrange(STREAM)
    )


def test_run_publisher_logs_redis_error_and_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def fake_publish(_client: object) -> int:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RedisError("down")
        raise RuntimeError("stop")

    monkeypatch.setattr("app.publisher.publish_pending", fake_publish)
    monkeypatch.setattr(
        "app.publisher.Redis.from_url", lambda *_args, **_kwargs: object()
    )
    monkeypatch.setattr("app.publisher.time.sleep", lambda _seconds: None)
    with pytest.raises(RuntimeError, match="stop"):
        run_publisher()
    assert calls["n"] == 2
