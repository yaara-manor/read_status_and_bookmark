import uuid

from contracts import UserCreated, UserMessage
from sqlmodel import Session

from app.core.db import engine
from app.models import Outbox
from app.outbox import write_outbox


def test_write_outbox_is_invisible_until_commit() -> None:
    user_id = uuid.uuid4()
    message = UserMessage(
        event_name="UserCreated",
        payload=UserCreated(
            id=user_id, display_name="ada@example.com", is_superuser=False
        ),
    )
    with Session(engine) as caller:
        write_outbox(caller, message)
        pending = [
            row
            for row in caller.new
            if isinstance(row, Outbox) and str(row.payload.get("id")) == str(user_id)
        ]
        assert len(pending) == 1
        new_id = pending[0].id
        with Session(engine) as other:
            assert other.get(Outbox, new_id) is None
        caller.commit()
    with Session(engine) as other:
        row = other.get(Outbox, new_id)
        assert row is not None
        assert row.published_at is None
        assert row.event_name == "UserCreated"
