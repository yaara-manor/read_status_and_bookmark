import uuid

import pytest
import redis
from contracts import (
    DEAD_STREAM,
    UserCreated,
    UserDeleted,
    UserMessage,
    UserUpdated,
    dump_message,
)
from sqlmodel import Session, select

from app.consumer import (
    _apply,
    _claimed,
    _drain,
    _ensure_group,
    _entries,
    _handle,
    _read_entries,
    _times_delivered,
    run_consumer,
)
from app.models import Event
from tests.test_consumer import _clear_main_hall
from tests.utils.event import create_random_event


class _Stub:
    def __init__(self) -> None:
        self.acks: list[str] = []
        self.dead: list[tuple[str, dict[str, str]]] = []
        self.pending: list[dict[str, int]] = []
        self.claim_queue: list[tuple[str, list[tuple[str, dict[str, object]]]]] = []
        self.read_response: object = []
        self.create_error: Exception | None = None
        self.autoclaim_calls = 0

    def xgroup_create(self, *args: object, **kwargs: object) -> None:
        if self.create_error is not None:
            raise self.create_error

    def xautoclaim(self, *args: object, **kwargs: object) -> tuple[str, list[object]]:
        self.autoclaim_calls += 1
        if self.claim_queue:
            return self.claim_queue.pop(0)
        return ("0-0", [])

    def xreadgroup(self, *args: object, **kwargs: object) -> object:
        return self.read_response

    def xpending_range(self, *args: object, **kwargs: object) -> list[dict[str, int]]:
        return self.pending

    def xadd(self, stream: str, fields: dict[str, str]) -> str:
        self.dead.append((stream, fields))
        return "1-0"

    def xack(self, stream: str, group: str, message_id: str) -> int:
        self.acks.append(message_id)
        return 1


def _created(superuser: bool) -> str:
    return dump_message(
        UserMessage(
            event_name="UserCreated",
            payload=UserCreated(
                id=uuid.uuid4(),
                display_name="Ada",
                is_superuser=superuser,
            ),
        )
    )


def test_apply_user_created_through_apply_seeds_when_superuser(db: Session) -> None:
    _clear_main_hall(db)
    owner_id = uuid.uuid4()
    _apply(
        db,
        UserMessage(
            event_name="UserCreated",
            payload=UserCreated(
                id=owner_id, display_name="Ada Lovelace", is_superuser=True
            ),
        ),
    )
    event = db.exec(select(Event).where(Event.name == "Opening Night")).one()
    assert event.owner_id == owner_id


def test_apply_rejects_mismatched_created_payload(db: Session) -> None:
    message = UserMessage.model_construct(
        event_name="UserCreated", payload=UserDeleted(id=uuid.uuid4())
    )
    with pytest.raises(ValueError, match="payload does not match event_name"):
        _apply(db, message)


def test_apply_user_updated_through_apply_renames_creator(db: Session) -> None:
    owner_id = uuid.uuid4()
    owned = create_random_event(db, creator="Old Name", owner_id=owner_id)
    _apply(
        db,
        UserMessage(
            event_name="UserUpdated",
            payload=UserUpdated(id=owner_id, display_name="New Name"),
        ),
    )
    db.expire_all()
    updated = db.get(Event, owned.id)
    assert updated is not None
    assert updated.creator == "New Name"


def test_apply_rejects_mismatched_updated_payload(db: Session) -> None:
    message = UserMessage.model_construct(
        event_name="UserUpdated", payload=UserDeleted(id=uuid.uuid4())
    )
    with pytest.raises(ValueError, match="payload does not match event_name"):
        _apply(db, message)


def test_apply_user_deleted_through_apply_removes_owned_event(db: Session) -> None:
    owner_id = uuid.uuid4()
    owned = create_random_event(db, creator="Owner", owner_id=owner_id)
    _apply(db, UserMessage(event_name="UserDeleted", payload=UserDeleted(id=owner_id)))
    db.expire_all()
    assert db.get(Event, owned.id) is None


def test_apply_rejects_mismatched_deleted_payload(db: Session) -> None:
    message = UserMessage.model_construct(
        event_name="UserDeleted",
        payload=UserUpdated(id=uuid.uuid4(), display_name="Ada"),
    )
    with pytest.raises(ValueError, match="payload does not match event_name"):
        _apply(db, message)


def test_apply_rejects_unknown_event_name(db: Session) -> None:
    message = UserMessage.model_construct(
        event_name="Other", payload=UserDeleted(id=uuid.uuid4())
    )
    with pytest.raises(AssertionError):
        _apply(db, message)


def test_entries_ignores_non_list() -> None:
    assert _entries(None) == []


def test_read_entries_ignores_non_list() -> None:
    assert _read_entries(None) == []


def test_read_entries_extracts_stream_block() -> None:
    raw = _created(False)
    entries = _read_entries([["user-events", [("3-0", {"data": raw})]]])
    assert entries == [("3-0", {"data": raw})]


def test_claimed_ignores_short_response() -> None:
    assert _claimed(None) == ("0-0", [])


def test_ensure_group_swallows_busygroup() -> None:
    stub = _Stub()
    stub.create_error = redis.ResponseError(
        "BUSYGROUP Consumer Group name already exists"
    )
    assert _ensure_group(stub) is None  # type: ignore[arg-type]


def test_ensure_group_reraises_other_response_error() -> None:
    stub = _Stub()
    stub.create_error = redis.ResponseError("NOGROUP")
    with pytest.raises(redis.ResponseError, match="NOGROUP"):
        _ensure_group(stub)  # type: ignore[arg-type]


def test_times_delivered_defaults_when_pending_empty() -> None:
    stub = _Stub()
    assert _times_delivered(stub, "1-0") == 1  # type: ignore[arg-type]


def test_handle_acks_valid_message() -> None:
    stub = _Stub()
    stub.pending = [{"times_delivered": 1}]
    _handle(stub, "4-0", {"data": _created(False)})  # type: ignore[arg-type]
    assert stub.acks == ["4-0"]
    assert stub.dead == []


def test_handle_retries_invalid_payload() -> None:
    stub = _Stub()
    _handle(stub, "4-1", {"data": "not-json"})  # type: ignore[arg-type]
    assert stub.acks == []
    assert stub.dead == []


def test_handle_non_string_data_is_treated_as_empty() -> None:
    stub = _Stub()
    stub.pending = [{"times_delivered": 5}]
    _handle(stub, "4-2", {"data": 1})  # type: ignore[arg-type]
    assert stub.dead == [(DEAD_STREAM, {"data": ""})]
    assert stub.acks == ["4-2"]


def test_drain_handles_claimed_message_then_stops() -> None:
    stub = _Stub()
    stub.pending = [{"times_delivered": 1}]
    stub.claim_queue = [("0-0", [("9-0", {"data": _created(False)})])]
    _drain(stub, "consumer-1")  # type: ignore[arg-type]
    assert stub.acks == ["9-0"]


def test_drain_handles_read_group_message() -> None:
    stub = _Stub()
    stub.pending = [{"times_delivered": 1}]
    stub.read_response = [["user-events", [("7-0", {"data": _created(False)})]]]
    _drain(stub, "consumer-1")  # type: ignore[arg-type]
    assert stub.acks == ["7-0"]


def test_drain_walks_claim_cursor_until_zero() -> None:
    stub = _Stub()
    stub.pending = [{"times_delivered": 1}]
    stub.claim_queue = [
        ("1-0", [("8-0", {"data": _created(False)})]),
        ("0-0", []),
    ]
    _drain(stub, "consumer-1")  # type: ignore[arg-type]
    assert stub.acks == ["8-0"]
    assert stub.autoclaim_calls == 2


def test_run_consumer_drains_once_then_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    class _DrainOnce:
        def __init__(self) -> None:
            self.groups = 0

        def xgroup_create(self, *args: object, **kwargs: object) -> None:
            self.groups += 1
            if self.groups > 1:
                raise RuntimeError("stop")

        def xautoclaim(
            self, *args: object, **kwargs: object
        ) -> tuple[str, list[object]]:
            return ("0-0", [])

        def xreadgroup(self, *args: object, **kwargs: object) -> list[object]:
            return []

    client = _DrainOnce()
    monkeypatch.setattr("app.consumer._client", lambda: client)
    with pytest.raises(RuntimeError, match="stop"):
        run_consumer()
    assert client.groups == 2


def test_run_consumer_reconnects_after_redis_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clients: list[object] = []

    class _Boom:
        def xgroup_create(self, *args: object, **kwargs: object) -> None:
            raise redis.RedisError("down")

    class _Stop:
        def xgroup_create(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("stop")

    sequence: list[object] = [_Boom(), _Stop()]

    def _client() -> object:
        client = sequence.pop(0)
        clients.append(client)
        return client

    monkeypatch.setattr("app.consumer._client", _client)
    monkeypatch.setattr("app.consumer.time.sleep", lambda _seconds: None)
    with pytest.raises(RuntimeError, match="stop"):
        run_consumer()
    assert len(clients) == 2
