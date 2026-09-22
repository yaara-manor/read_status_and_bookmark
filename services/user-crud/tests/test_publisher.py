import asyncio
import uuid
from datetime import UTC, datetime

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
    with Session(engine) as session:
        pending = session.exec(
            select(Outbox).where(Outbox.published_at.is_(None))
        ).all()
        now = datetime.now(UTC)
        for row in pending:
            row.published_at = now
        session.commit()

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

    client = Redis.from_url(settings.REDIS_URL)
    assert publish_pending(client) == 1

    with Session(engine) as session:
        stored = session.get(Outbox, row_id)
        assert stored is not None
        assert stored.published_at is not None

    payload = dump_message(message)
    entries = client.xrange(STREAM)
    assert any(fields.get(b"data") == payload.encode() for _, fields in entries)

    assert publish_pending(client) == 0


def test_run_publisher_logs_redis_error_and_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def fake_publish(_client: object) -> int:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RedisError("down")
        raise asyncio.CancelledError

    monkeypatch.setattr("app.publisher.publish_pending", fake_publish)
    monkeypatch.setattr("app.publisher.Redis.from_url", lambda _url: object())

    async def _sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.publisher.asyncio.sleep", _sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_publisher())
    assert calls["n"] == 2
