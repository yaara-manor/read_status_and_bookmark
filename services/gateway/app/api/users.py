from contracts import UpdatePassword, UserCreate, UserUpdate, UserUpdateMe
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.config import settings
from app.forward import CallerDep, proxy

router = APIRouter(tags=["users"])


@router.get("/users")
async def read_users(request: Request, caller: CallerDep) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.post("/users")
async def create_user(
    request: Request, body: UserCreate, caller: CallerDep
) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.patch("/users/me")
async def update_user_me(
    request: Request, body: UserUpdateMe, caller: CallerDep
) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.patch("/users/me/password")
async def update_password_me(
    request: Request, body: UpdatePassword, caller: CallerDep
) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.get("/users/me")
async def read_user_me(request: Request, caller: CallerDep) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.delete("/users/me")
async def delete_user_me(request: Request, caller: CallerDep) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.get("/users/{user_id}")
async def read_user_by_id(
    request: Request, user_id: str, caller: CallerDep
) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.patch("/users/{user_id}")
async def update_user(
    request: Request, user_id: str, body: UserUpdate, caller: CallerDep
) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.delete("/users/{user_id}")
async def delete_user(request: Request, user_id: str, caller: CallerDep) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)
