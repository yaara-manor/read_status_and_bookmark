import uuid

from contracts import EventCreate, TicketAvailability
from sqlmodel import Session

from app.models import Event, Performer, Ticket, Venue


def create_event(
    *, session: Session, event_in: EventCreate, owner_id: uuid.UUID, creator: str
) -> Event:
    venue = session.get(Venue, event_in.venue_id)
    if venue is None:
        raise LookupError("Venue")
    performer = session.get(Performer, event_in.performer_id)
    if performer is None:
        raise LookupError("Performer")
    if not venue.seat_map or any(width < 1 for width in venue.seat_map):
        raise ValueError("Invalid seat map")
    db_event = Event.model_validate(
        event_in.model_dump(exclude={"price"}),
        update={"owner_id": owner_id, "creator": creator},
    )
    session.add(db_event)
    session.flush()
    session.add_all(
        [
            Ticket(
                event_id=db_event.id,
                row=row,
                seat=seat,
                price=event_in.price,
                availability=TicketAvailability.AVAILABLE,
            )
            for row, width in enumerate(venue.seat_map)
            for seat in range(width)
        ]
    )
    session.commit()
    session.refresh(db_event)
    return db_event
