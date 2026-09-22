import uuid
from typing import Any

from contracts import (
    Caller,
    EventBookmarkUpdate,
    EventCreate,
    EventDetail,
    EventPublic,
    EventsPublic,
    EventUpdate,
    Message,
    TicketPublic,
)
from fastapi import APIRouter, HTTPException
from sqlmodel import Session, col, func, select

from app import crud
from app.api.deps import CallerDep, SessionDep
from app.models import Event, EventBookmarkLink, EventReadLink, Ticket

router = APIRouter(prefix="/events", tags=["events"])


def event_public(event: Event, *, is_read: bool, is_bookmarked: bool) -> EventPublic:
    return EventPublic(
        name=event.name,
        description=event.description,
        id=event.id,
        owner_id=event.owner_id,
        venue_id=event.venue_id,
        performer_id=event.performer_id,
        time=event.time,
        created_at=event.created_at,
        creator=event.creator,
        is_read=is_read,
        is_bookmarked=is_bookmarked,
    )


def _link_event_ids(
    session: Session,
    model: type[EventReadLink] | type[EventBookmarkLink],
    user_id: uuid.UUID,
    event_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    if not event_ids:
        return set()
    return set(
        session.exec(
            select(model.event_id).where(
                model.user_id == user_id,
                col(model.event_id).in_(event_ids),
            )
        ).all()
    )


def _tickets(session: Session, event_id: uuid.UUID) -> list[Ticket]:
    return list(session.exec(select(Ticket).where(Ticket.event_id == event_id)).all())


def _event_detail(
    event: Event, tickets: list[Ticket], *, is_read: bool, is_bookmarked: bool
) -> EventDetail:
    public = event_public(event, is_read=is_read, is_bookmarked=is_bookmarked)
    return EventDetail(
        **public.model_dump(),
        tickets=[
            TicketPublic.model_validate(ticket, from_attributes=True)
            for ticket in tickets
        ],
    )


def _require_editor(caller: Caller, event: Event) -> None:
    if not caller.is_superuser and event.owner_id != caller.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")


@router.get("", response_model=EventsPublic)
def read_events(
    session: SessionDep, caller: CallerDep, skip: int = 0, limit: int = 100
) -> Any:
    count = session.exec(select(func.count()).select_from(Event)).one()
    events = session.exec(
        select(Event).order_by(col(Event.created_at).desc()).offset(skip).limit(limit)
    ).all()
    event_ids = [event.id for event in events]
    read_ids = _link_event_ids(session, EventReadLink, caller.id, event_ids)
    bookmark_ids = _link_event_ids(session, EventBookmarkLink, caller.id, event_ids)
    return EventsPublic(
        data=[
            event_public(
                event,
                is_read=event.id in read_ids,
                is_bookmarked=event.id in bookmark_ids,
            )
            for event in events
        ],
        count=count,
    )


@router.get("/bookmarked", response_model=EventsPublic)
def read_bookmarked_events(
    session: SessionDep, caller: CallerDep, skip: int = 0, limit: int = 100
) -> Any:
    count = session.exec(
        select(func.count())
        .select_from(EventBookmarkLink)
        .where(EventBookmarkLink.user_id == caller.id)
    ).one()
    events = session.exec(
        select(Event)
        .join(EventBookmarkLink, col(EventBookmarkLink.event_id) == Event.id)
        .where(EventBookmarkLink.user_id == caller.id)
        .order_by(col(Event.created_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    read_ids = _link_event_ids(
        session, EventReadLink, caller.id, [event.id for event in events]
    )
    return EventsPublic(
        data=[
            event_public(event, is_read=event.id in read_ids, is_bookmarked=True)
            for event in events
        ],
        count=count,
    )


@router.get("/{id}", response_model=EventDetail)
def read_event(session: SessionDep, caller: CallerDep, id: uuid.UUID) -> Any:
    event = session.get(Event, id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    link = session.get(EventReadLink, (caller.id, event.id))
    if link is None:
        session.add(EventReadLink(user_id=caller.id, event_id=event.id))
        session.commit()
        session.refresh(event)
    is_bookmarked = session.get(EventBookmarkLink, (caller.id, event.id)) is not None
    return _event_detail(
        event,
        _tickets(session, event.id),
        is_read=True,
        is_bookmarked=is_bookmarked,
    )


@router.put("/{id}/bookmark", response_model=EventPublic)
def set_event_bookmark(
    *,
    session: SessionDep,
    caller: CallerDep,
    id: uuid.UUID,
    body: EventBookmarkUpdate,
) -> Any:
    event = session.get(Event, id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    link = session.get(EventBookmarkLink, (caller.id, event.id))
    if body.is_bookmarked and link is None:
        session.add(EventBookmarkLink(user_id=caller.id, event_id=event.id))
        session.commit()
    elif not body.is_bookmarked and link is not None:
        session.delete(link)
        session.commit()
    is_read = session.get(EventReadLink, (caller.id, event.id)) is not None
    return event_public(event, is_read=is_read, is_bookmarked=body.is_bookmarked)


@router.post("", response_model=EventPublic)
def create_event(
    *, session: SessionDep, caller: CallerDep, event_in: EventCreate
) -> Any:
    try:
        event = crud.create_event(
            session=session,
            event_in=event_in,
            owner_id=caller.id,
            creator=caller.display_name,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=f"{exc} not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return event_public(event, is_read=False, is_bookmarked=False)


@router.put("/{id}", response_model=EventPublic)
def update_event(
    *,
    session: SessionDep,
    caller: CallerDep,
    id: uuid.UUID,
    event_in: EventUpdate,
) -> Any:
    event = session.get(Event, id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_editor(caller, event)
    event.sqlmodel_update(event_in.model_dump(exclude_unset=True))
    session.add(event)
    session.commit()
    session.refresh(event)
    is_read = session.get(EventReadLink, (caller.id, event.id)) is not None
    is_bookmarked = session.get(EventBookmarkLink, (caller.id, event.id)) is not None
    return event_public(event, is_read=is_read, is_bookmarked=is_bookmarked)


@router.delete("/{id}")
def delete_event(session: SessionDep, caller: CallerDep, id: uuid.UUID) -> Message:
    event = session.get(Event, id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_editor(caller, event)
    session.delete(event)
    session.commit()
    return Message(message="Event deleted successfully")
