from contracts import EventBookmarkUpdate, EventUpdate
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.config import settings
from app.forward import CallerDep, proxy

router = APIRouter(tags=["events"])


@router.get("/events")
async def read_events(request: Request, caller: CallerDep) -> Response:
    return await proxy(request, settings.EVENT_CRUD_URL, caller)


@router.get("/events/bookmarked")
async def read_bookmarked_events(request: Request, caller: CallerDep) -> Response:
    return await proxy(request, settings.EVENT_CRUD_URL, caller)


@router.get("/events/{id}")
async def read_event(request: Request, id: str, caller: CallerDep) -> Response:
    return await proxy(request, settings.EVENT_CRUD_URL, caller)


@router.put("/events/{id}/bookmark")
async def set_event_bookmark(
    request: Request, id: str, body: EventBookmarkUpdate, caller: CallerDep
) -> Response:
    return await proxy(request, settings.EVENT_CRUD_URL, caller)


@router.post("/events")
async def create_event(request: Request, caller: CallerDep) -> Response:
    return await proxy(request, settings.EVENT_CRUD_URL, caller)


@router.put("/events/{id}")
async def update_event(
    request: Request, id: str, body: EventUpdate, caller: CallerDep
) -> Response:
    return await proxy(request, settings.EVENT_CRUD_URL, caller)


@router.delete("/events/{id}")
async def delete_event(request: Request, id: str, caller: CallerDep) -> Response:
    return await proxy(request, settings.EVENT_CRUD_URL, caller)
