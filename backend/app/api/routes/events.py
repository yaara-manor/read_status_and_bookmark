import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel, col, func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Event,
    EventBookmarkLink,
    EventBookmarkUpdate,
    EventCreate,
    EventDetail,
    EventPublic,
    EventReadLink,
    EventsPublic,
    EventUpdate,
    Message,
    TicketPublic,
)

router = APIRouter(prefix="/events", tags=["events"])


def _link_event_ids(
    session: SessionDep,
    model: type[SQLModel],
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


def _event_flags(
    session: SessionDep, user_id: uuid.UUID, event_id: uuid.UUID
) -> tuple[bool, bool]:
    is_read = session.get(EventReadLink, (user_id, event_id)) is not None
    is_bookmarked = session.get(EventBookmarkLink, (user_id, event_id)) is not None
    return is_read, is_bookmarked


def _event_detail(
    event: Event, *, is_read: bool, is_bookmarked: bool
) -> EventDetail:
    public = EventPublic.from_event(
        event, is_read=is_read, is_bookmarked=is_bookmarked
    )
    return EventDetail(
        **public.model_dump(),
        tickets=[TicketPublic.model_validate(ticket) for ticket in event.tickets],
    )


@router.get("/", response_model=EventsPublic)
def read_events(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve events.
    """
    count = session.exec(select(func.count()).select_from(Event)).one()
    statement = (
        select(Event)
        .options(selectinload(Event.owner))
        .order_by(col(Event.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    events = session.exec(statement).all()
    event_ids = [event.id for event in events]
    read_ids = _link_event_ids(session, EventReadLink, current_user.id, event_ids)
    bookmark_ids = _link_event_ids(
        session, EventBookmarkLink, current_user.id, event_ids
    )
    events_public = [
        EventPublic.from_event(
            event,
            is_read=event.id in read_ids,
            is_bookmarked=event.id in bookmark_ids,
        )
        for event in events
    ]
    return EventsPublic(data=events_public, count=count)


@router.get("/bookmarked", response_model=EventsPublic)
def read_bookmarked_events(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve the current user's bookmarked events.
    """
    count = session.exec(
        select(func.count())
        .select_from(EventBookmarkLink)
        .where(EventBookmarkLink.user_id == current_user.id)
    ).one()
    events = session.exec(
        select(Event)
        .join(EventBookmarkLink)
        .where(EventBookmarkLink.user_id == current_user.id)
        .options(selectinload(Event.owner))
        .order_by(col(Event.created_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    read_ids = _link_event_ids(
        session, EventReadLink, current_user.id, [event.id for event in events]
    )
    return EventsPublic(
        data=[
            EventPublic.from_event(
                event, is_read=event.id in read_ids, is_bookmarked=True
            )
            for event in events
        ],
        count=count,
    )


@router.get("/{id}", response_model=EventDetail)
def read_event(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get event by ID.
    """
    event = session.get(Event, id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    link = session.get(EventReadLink, (current_user.id, event.id))
    if link is None:
        session.add(EventReadLink(user_id=current_user.id, event_id=event.id))
        session.commit()
    is_bookmarked = (
        session.get(EventBookmarkLink, (current_user.id, event.id)) is not None
    )
    return _event_detail(event, is_read=True, is_bookmarked=is_bookmarked)


@router.put("/{id}/bookmark", response_model=EventPublic)
def set_event_bookmark(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    body: EventBookmarkUpdate,
) -> Any:
    """
    Set or unset the current user's bookmark for an event.
    """
    event = session.get(Event, id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    link = session.get(EventBookmarkLink, (current_user.id, event.id))
    if body.is_bookmarked and link is None:
        session.add(EventBookmarkLink(user_id=current_user.id, event_id=event.id))
        session.commit()
    elif not body.is_bookmarked and link is not None:
        session.delete(link)
        session.commit()
    is_read = session.get(EventReadLink, (current_user.id, event.id)) is not None
    return EventPublic.from_event(
        event, is_read=is_read, is_bookmarked=body.is_bookmarked
    )


@router.post("/", response_model=EventPublic)
def create_event(
    *, session: SessionDep, current_user: CurrentUser, event_in: EventCreate
) -> Any:
    """
    Create new event.
    """
    try:
        event = crud.create_event(
            session=session, event_in=event_in, owner_id=current_user.id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=f"{exc} not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EventPublic.from_event(event)


@router.put("/{id}", response_model=EventPublic)
def update_event(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    event_in: EventUpdate,
) -> Any:
    """
    Update an event.
    """
    event = session.get(Event, id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not current_user.is_superuser and (event.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_dict = event_in.model_dump(exclude_unset=True)
    event.sqlmodel_update(update_dict)
    session.add(event)
    session.commit()
    session.refresh(event)
    is_read, is_bookmarked = _event_flags(session, current_user.id, event.id)
    return EventPublic.from_event(
        event, is_read=is_read, is_bookmarked=is_bookmarked
    )


@router.delete("/{id}")
def delete_event(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an event.
    """
    event = session.get(Event, id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not current_user.is_superuser and (event.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(event)
    session.commit()
    return Message(message="Event deleted successfully")
