import logging
import os
import time
from datetime import UTC, datetime
from typing import Literal, assert_never

import redis
from contracts import (
    CONSUMER_GROUP,
    DEAD_STREAM,
    STREAM,
    EventCreate,
    PerformerGenre,
    UserCreated,
    UserDeleted,
    UserMessage,
    UserUpdated,
    load_message,
)
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.core.db import engine
from app.models import Event, EventBookmarkLink, EventReadLink, Performer, Ticket, Venue

logger = logging.getLogger(__name__)

# ponytail: pending messages are retried only after 60s idle so five failures are
# not burned in one tight loop. Upgrade: a shorter idle with a single consumer.
_CLAIM_IDLE_MS = 60_000
_BATCH = 16
_BLOCK_MS = 5_000
_RETRY_SECONDS = 1

_Entry = tuple[str, dict[str, str]]


def outcome(handled: bool, times_delivered: int) -> Literal["ack", "retry", "dead"]:
    if handled:
        return "ack"
    if times_delivered >= 5:
        return "dead"
    return "retry"


def apply_user_created(session: Session, payload: UserCreated) -> None:
    if not payload.is_superuser:
        return
    # ponytail: venue.name is not unique, so two overlapping superuser messages can
    # both seed. Upgrade: a unique index on venue.name.
    if session.exec(select(Venue).where(Venue.name == "Main Hall")).first() is not None:
        return
    venue = Venue(
        name="Main Hall",
        city="Tel Aviv",
        country="Israel",
        seat_map=[4, 5, 5, 7],
    )
    performer = Performer(
        name="The Band",
        genre=PerformerGenre.MUSIC,
        description="Live music",
    )
    session.add(venue)
    session.add(performer)
    session.flush()
    crud.create_event(
        session=session,
        event_in=EventCreate(
            name="Opening Night",
            description="First show of the season",
            venue_id=venue.id,
            performer_id=performer.id,
            time=datetime(2026, 10, 1, 20, 0, tzinfo=UTC),
            price=25.0,
        ),
        owner_id=payload.id,
        creator=payload.display_name,
    )


def apply_user_updated(session: Session, payload: UserUpdated) -> None:
    for event in session.exec(select(Event).where(Event.owner_id == payload.id)):
        event.creator = payload.display_name
        session.add(event)
    session.commit()


def apply_user_deleted(session: Session, payload: UserDeleted) -> None:
    for event in session.exec(select(Event).where(Event.owner_id == payload.id)):
        session.delete(event)
    session.flush()
    session.expire_all()
    for read_link in session.exec(
        select(EventReadLink).where(EventReadLink.user_id == payload.id)
    ):
        session.delete(read_link)
    for bookmark_link in session.exec(
        select(EventBookmarkLink).where(EventBookmarkLink.user_id == payload.id)
    ):
        session.delete(bookmark_link)
    for ticket in session.exec(select(Ticket).where(Ticket.user_id == payload.id)):
        ticket.user_id = None
        session.add(ticket)
    session.commit()


def _apply(session: Session, message: UserMessage) -> None:
    payload = message.payload
    match message.event_name:
        case "UserCreated":
            if not isinstance(payload, UserCreated):
                raise ValueError("payload does not match event_name")
            apply_user_created(session, payload)
        case "UserUpdated":
            if not isinstance(payload, UserUpdated):
                raise ValueError("payload does not match event_name")
            apply_user_updated(session, payload)
        case "UserDeleted":
            if not isinstance(payload, UserDeleted):
                raise ValueError("payload does not match event_name")
            apply_user_deleted(session, payload)
        case _ as unreachable:
            assert_never(unreachable)


def _client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _ensure_group(client: redis.Redis) -> None:
    try:
        client.xgroup_create(STREAM, CONSUMER_GROUP, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def _entries(messages: object) -> list[_Entry]:
    if not isinstance(messages, list):
        return []
    entries: list[_Entry] = []
    for message in messages:
        if (
            isinstance(message, (list, tuple))
            and len(message) == 2
            and isinstance(message[0], str)
            and isinstance(message[1], dict)
        ):
            entries.append((message[0], message[1]))
    return entries


def _read_entries(response: object) -> list[_Entry]:
    if not isinstance(response, list):
        return []
    entries: list[_Entry] = []
    for block in response:
        if isinstance(block, (list, tuple)) and len(block) == 2:
            entries.extend(_entries(block[1]))
    return entries


def _claimed(response: object) -> tuple[str, list[_Entry]]:
    if not isinstance(response, (list, tuple)) or len(response) < 2:
        return "0-0", []
    cursor = response[0] if isinstance(response[0], str) else "0-0"
    return cursor, _entries(response[1])


def _times_delivered(client: redis.Redis, message_id: str) -> int:
    pending = client.xpending_range(STREAM, CONSUMER_GROUP, message_id, message_id, 1)
    if isinstance(pending, list) and pending and isinstance(pending[0], dict):
        return int(pending[0]["times_delivered"])
    return 1


def _handle(client: redis.Redis, message_id: str, fields: dict[str, str]) -> None:
    raw = fields.get("data")
    if not isinstance(raw, str):
        raw = ""
    try:
        message = load_message(raw)
        with Session(engine) as session:
            _apply(session, message)
        handled = True
    except Exception:
        logger.exception("user event %s failed", message_id)
        handled = False
    decision = outcome(handled, _times_delivered(client, message_id))
    if decision == "retry":
        return
    if decision == "dead":
        client.xadd(DEAD_STREAM, {"data": raw})
    client.xack(STREAM, CONSUMER_GROUP, message_id)


def _drain(client: redis.Redis, consumer: str) -> None:
    cursor = "0-0"
    while True:
        cursor, messages = _claimed(
            client.xautoclaim(
                STREAM,
                CONSUMER_GROUP,
                consumer,
                _CLAIM_IDLE_MS,
                cursor,
                count=_BATCH,
            )
        )
        for message_id, fields in messages:
            _handle(client, message_id, fields)
        if not messages or cursor == "0-0":
            break
    for message_id, fields in _read_entries(
        client.xreadgroup(
            CONSUMER_GROUP,
            consumer,
            {STREAM: ">"},
            count=_BATCH,
            block=_BLOCK_MS,
        )
    ):
        _handle(client, message_id, fields)


def run_consumer() -> None:
    client = _client()
    consumer = f"event-crud-{os.getpid()}"
    while True:
        try:
            _ensure_group(client)
            _drain(client, consumer)
        except redis.RedisError:
            logger.exception("redis outage")
            time.sleep(_RETRY_SECONDS)
            client = _client()
