from datetime import UTC, datetime

import pytest
from sqlmodel import Session, func, select

from app import crud
from app.models import Event, EventCreate, Ticket, TicketAvailability
from tests.utils.event import create_performer, create_venue
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def _event_in(venue_id, performer_id, *, price: float = 25.0) -> EventCreate:
    return EventCreate(
        name=random_lower_string(),
        description=random_lower_string(),
        venue_id=venue_id,
        performer_id=performer_id,
        time=datetime(2026, 10, 1, 20, 0, tzinfo=UTC),
        price=price,
    )


def test_create_event_writes_one_ticket_per_seat(db: Session) -> None:
    owner = create_random_user(db)
    venue = create_venue(db, seat_map=[4, 5, 5, 7])
    performer = create_performer(db)

    event = crud.create_event(
        session=db, event_in=_event_in(venue.id, performer.id), owner_id=owner.id
    )

    tickets = db.exec(select(Ticket).where(Ticket.event_id == event.id)).all()
    assert len(tickets) == 21
    seat = next(ticket for ticket in tickets if ticket.row == 0 and ticket.seat == 2)
    assert seat.price == 25.0
    assert seat.availability == TicketAvailability.AVAILABLE
    assert seat.user_id is None


def test_create_event_rejects_zero_width_row(db: Session) -> None:
    owner = create_random_user(db)
    venue = create_venue(db, seat_map=[0])
    performer = create_performer(db)
    count_before = db.exec(select(func.count()).select_from(Event)).one()

    with pytest.raises(ValueError, match="Invalid seat map"):
        crud.create_event(
            session=db, event_in=_event_in(venue.id, performer.id), owner_id=owner.id
        )

    count_after = db.exec(select(func.count()).select_from(Event)).one()
    assert count_after == count_before
