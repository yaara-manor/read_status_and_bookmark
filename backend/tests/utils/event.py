from datetime import UTC, datetime

from sqlmodel import Session

from app import crud
from app.models import Event, EventCreate, Performer, PerformerGenre, Venue
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def create_venue(db: Session, *, seat_map: list[int] | None = None) -> Venue:
    venue = Venue(
        name=random_lower_string(),
        city=random_lower_string(),
        country=random_lower_string(),
        seat_map=seat_map if seat_map is not None else [1],
    )
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


def create_performer(db: Session) -> Performer:
    performer = Performer(
        name=random_lower_string(),
        genre=PerformerGenre.MUSIC,
        description=random_lower_string(),
    )
    db.add(performer)
    db.commit()
    db.refresh(performer)
    return performer


def create_random_event(db: Session) -> Event:
    user = create_random_user(db)
    owner_id = user.id
    assert owner_id is not None
    venue = create_venue(db)
    performer = create_performer(db)
    event_in = EventCreate(
        name=random_lower_string(),
        description=random_lower_string(),
        venue_id=venue.id,
        performer_id=performer.id,
        time=datetime(2026, 10, 1, 20, 0, tzinfo=UTC),
        price=10.0,
    )
    return crud.create_event(session=db, event_in=event_in, owner_id=owner_id)
