import uuid
from datetime import UTC, datetime

import pytest
from contracts import (
    PerformerGenre,
    TicketAvailability,
    UserCreated,
    UserDeleted,
    UserMessage,
    UserUpdated,
)
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.consumer import _apply, apply_user_deleted, apply_user_updated, outcome
from app.models import (
    Event,
    EventBookmarkLink,
    EventReadLink,
    Performer,
    Ticket,
    Venue,
)
from app.seed import seed_demo
from tests.utils.event import create_random_event


def _main_hall(db: Session) -> Venue | None:
    return db.exec(select(Venue).where(Venue.name == "Main Hall")).first()


def _clear_main_hall(db: Session) -> None:
    venue = _main_hall(db)
    if venue is None:
        return
    for event in db.exec(select(Event).where(Event.venue_id == venue.id)):
        db.delete(event)
    db.flush()
    for performer in db.exec(select(Performer).where(Performer.name == "The Band")):
        still_used = db.exec(
            select(func.count())
            .select_from(Event)
            .where(Event.performer_id == performer.id)
        ).one()
        if still_used == 0:
            db.delete(performer)
    db.delete(venue)
    db.commit()


def test_superuser_created_seeds_opening_night(db: Session) -> None:
    _clear_main_hall(db)
    owner_id = uuid.uuid4()
    seed_demo(db, owner_id, "Ada Lovelace")

    venue = _main_hall(db)
    assert venue is not None
    assert venue.city == "Tel Aviv"
    assert venue.country == "Israel"
    assert venue.seat_map == [4, 5, 5, 7]

    performer = db.exec(select(Performer).where(Performer.name == "The Band")).one()
    assert performer.genre == PerformerGenre.MUSIC
    assert performer.description == "Live music"

    event = db.exec(select(Event).where(Event.name == "Opening Night")).one()
    assert event.description == "First show of the season"
    assert event.time == datetime(2026, 10, 1, 20, 0, tzinfo=UTC)
    assert event.owner_id == owner_id
    assert event.creator == "Ada Lovelace"
    assert event.venue_id == venue.id
    assert event.performer_id == performer.id

    tickets = db.exec(select(Ticket).where(Ticket.event_id == event.id)).all()
    assert len(tickets) == 21
    assert {ticket.price for ticket in tickets} == {25.0}
    assert {ticket.availability for ticket in tickets} == {TicketAvailability.AVAILABLE}


def test_non_superuser_created_does_not_seed(db: Session) -> None:
    _clear_main_hall(db)
    _apply(
        db,
        UserMessage(
            event_name="UserCreated",
            payload=UserCreated(
                id=uuid.uuid4(), display_name="Grace Hopper", is_superuser=False
            ),
        ),
    )
    assert _main_hall(db) is None
    assert db.exec(select(Event).where(Event.name == "Opening Night")).first() is None


def test_second_superuser_created_does_not_add_another_main_hall(db: Session) -> None:
    _clear_main_hall(db)
    first_id = uuid.uuid4()
    seed_demo(db, first_id, "Ada Lovelace")
    seed_demo(db, uuid.uuid4(), "Grace Hopper")

    halls = db.exec(select(Venue).where(Venue.name == "Main Hall")).all()
    assert len(halls) == 1
    event = db.exec(select(Event).where(Event.name == "Opening Night")).one()
    assert event.owner_id == first_id
    assert event.creator == "Ada Lovelace"


def test_seed_demo_rolls_back_when_venue_name_races(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_main_hall(db)
    real_flush = Session.flush

    def boom(self: Session, *args: object, **kwargs: object) -> None:
        if self.new:
            raise IntegrityError("INSERT", {}, Exception("uq_venue_name"))
        real_flush(self, *args, **kwargs)

    monkeypatch.setattr(Session, "flush", boom)
    seed_demo(db, uuid.uuid4(), "Ada")
    assert _main_hall(db) is None


def test_user_updated_changes_creator_only_for_that_owner(db: Session) -> None:
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    owned = create_random_event(db, creator="Old Name", owner_id=owner_id)
    other = create_random_event(db, creator="Other Name", owner_id=other_id)

    apply_user_updated(db, UserUpdated(id=owner_id, display_name="New Name"))

    db.expire_all()
    updated = db.get(Event, owned.id)
    untouched = db.get(Event, other.id)
    assert updated is not None
    assert untouched is not None
    assert updated.creator == "New Name"
    assert untouched.creator == "Other Name"


def test_user_deleted_removes_owned_rows_and_is_safe_to_repeat(db: Session) -> None:
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    owned = create_random_event(db, creator="Owner", owner_id=owner_id)
    other = create_random_event(db, creator="Other", owner_id=other_id)
    bought = db.exec(select(Ticket).where(Ticket.event_id == other.id)).one()
    bought.user_id = owner_id
    bought.availability = TicketAvailability.BOOKED
    db.add(EventBookmarkLink(user_id=owner_id, event_id=other.id))
    db.add(EventReadLink(user_id=owner_id, event_id=other.id))
    db.add(EventBookmarkLink(user_id=other_id, event_id=other.id))
    db.commit()

    payload = UserDeleted(id=owner_id)
    apply_user_deleted(db, payload)

    db.expire_all()
    assert db.get(Event, owned.id) is None
    assert db.get(Event, other.id) is not None
    assert (
        db.exec(
            select(EventBookmarkLink).where(EventBookmarkLink.user_id == owner_id)
        ).first()
        is None
    )
    assert (
        db.exec(select(EventReadLink).where(EventReadLink.user_id == owner_id)).first()
        is None
    )
    assert (
        db.exec(
            select(EventBookmarkLink).where(
                EventBookmarkLink.user_id == other_id,
                EventBookmarkLink.event_id == other.id,
            )
        ).first()
        is not None
    )
    kept = db.get(Ticket, bought.id)
    assert kept is not None
    assert kept.user_id is None
    assert kept.availability == TicketAvailability.BOOKED

    apply_user_deleted(db, payload)


def test_outcome_ack_retry_and_dead() -> None:
    assert outcome(True, 1) == "ack"
    assert outcome(False, 4) == "retry"
    assert outcome(False, 5) == "dead"
