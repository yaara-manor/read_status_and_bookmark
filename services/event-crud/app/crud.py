import uuid
from typing import overload

from contracts import EventCreate, TicketAvailability
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Event, Performer, Ticket, Venue


def name_prefix(q: str) -> str | None:
    stripped = q.strip().lower()
    if not stripped:
        return None
    return stripped.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def suggest_limit(limit: int) -> int:
    return min(max(limit, 1), 10)


@overload
def match_name_prefix(
    session: Session, model: type[Venue], q: str, limit: int
) -> list[Venue]: ...


@overload
def match_name_prefix(
    session: Session, model: type[Performer], q: str, limit: int
) -> list[Performer]: ...


def match_name_prefix(
    session: Session,
    model: type[Venue] | type[Performer],
    q: str,
    limit: int,
) -> list[Venue] | list[Performer]:
    prefix = name_prefix(q)
    if prefix is None:
        return []
    # ponytail: left-anchored lower(name) LIKE uses ix_*_lower_name up to millions of rows.
    # Upgrade: pg_trgm or a search service for contains or typo matching.
    column = func.lower(model.name)
    rows = session.exec(
        select(model)
        .where(column.like(f"{prefix}%", escape="\\"))
        .order_by(column, model.id)
        .limit(suggest_limit(limit))
    ).all()
    return list(rows)


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
