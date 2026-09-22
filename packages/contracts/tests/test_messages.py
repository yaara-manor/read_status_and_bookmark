import json
from uuid import UUID

import pytest
from contracts import (
    UserCreated,
    UserDeleted,
    UserMessage,
    UserUpdated,
    dump_message,
    load_message,
)

USER_ID = UUID("12345678-1234-5678-1234-567812345678")


def test_round_trip_each_user_message() -> None:
    messages = [
        UserMessage(
            event_name="UserCreated",
            payload=UserCreated(id=USER_ID, display_name="Ada", is_superuser=True),
        ),
        UserMessage(
            event_name="UserUpdated",
            payload=UserUpdated(id=USER_ID, display_name="Ada Lovelace"),
        ),
        UserMessage(
            event_name="UserDeleted",
            payload=UserDeleted(id=USER_ID),
        ),
    ]
    for message in messages:
        raw = dump_message(message)
        body = json.loads(raw)
        assert body["payload"]["id"] == str(USER_ID)
        assert load_message(raw) == message


def test_load_message_unknown_event_raises() -> None:
    with pytest.raises(ValueError):
        load_message('{"event_name": "NoSuch", "payload": {}}')


def test_load_message_mismatched_payload_raises() -> None:
    with pytest.raises(ValueError):
        load_message(
            '{"event_name": "UserCreated", "payload": {"id": "12345678-1234-5678-1234-567812345678"}}'
        )
