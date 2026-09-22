import uuid
from datetime import UTC, datetime

from contracts import EventCreate, PerformerGenre
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import crud
from app.models import Performer, Venue


def seed_demo(session: Session, owner_id: uuid.UUID, creator: str) -> None:
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
    try:
        session.flush()
    except IntegrityError:
        # ponytail: any integrity error here is treated as the venue-name race.
        # Upgrade: match the unique violation on venue.name only.
        session.rollback()
        return
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
        owner_id=owner_id,
        creator=creator,
    )
