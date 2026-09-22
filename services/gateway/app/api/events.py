from uuid import UUID

from contracts import (
    EventBookmarkUpdate,
    EventCreate,
    EventDetail,
    EventPublic,
    EventsPublic,
    EventUpdate,
    Message,
)
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.config import settings
from app.forward import CallerDep, proxy

router = APIRouter(tags=["events"])


@router.get("/events", response_model=EventsPublic)
async def read_events(
    request: Request, caller: CallerDep, skip: int = 0, limit: int = 100
) -> Response:
    return await proxy(request, settings.EVENT_CRUD_URL, caller)


@router.get("/events/bookmarked", response_model=EventsPublic)
async def read_bookmarked_events(
    request: Request, caller: CallerDep, skip: int = 0, limit: int = 100
) -> Response:
    return await proxy(request, settings.EVENT_CRUD_URL, caller)


@router.get("/events/{id}", response_model=EventDetail)
async def read_event(request: Request, id: UUID, caller: CallerDep) -> Response:
    return await proxy(request, settings.EVENT_CRUD_URL, caller)


@router.put("/events/{id}/bookmark", response_model=EventPublic)
async def set_event_bookmark(
    request: Request, id: UUID, body: EventBookmarkUpdate, caller: CallerDep
) -> Response:
    return await proxy(request, settings.EVENT_CRUD_URL, caller)


@router.post("/events", response_model=EventPublic)
async def create_event(
    request: Request, body: EventCreate, caller: CallerDep
) -> Response:
    return await proxy(request, settings.EVENT_CRUD_URL, caller)


@router.put("/events/{id}", response_model=EventPublic)
async def update_event(
    request: Request, id: UUID, body: EventUpdate, caller: CallerDep
) -> Response:
    return await proxy(request, settings.EVENT_CRUD_URL, caller)


@router.delete("/events/{id}", response_model=Message)
async def delete_event(request: Request, id: UUID, caller: CallerDep) -> Response:
    return await proxy(request, settings.EVENT_CRUD_URL, caller)
