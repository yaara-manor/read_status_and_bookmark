from uuid import UUID

from contracts import (
    Message,
    UpdatePassword,
    UserCreate,
    UserPublic,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.config import settings
from app.forward import CallerDep, proxy

router = APIRouter(tags=["users"])


@router.get("/users", response_model=UsersPublic)
async def read_users(
    request: Request, caller: CallerDep, skip: int = 0, limit: int = 100
) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.post("/users", response_model=UserPublic)
async def create_user(
    request: Request, body: UserCreate, caller: CallerDep
) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.patch("/users/me", response_model=UserPublic)
async def update_user_me(
    request: Request, body: UserUpdateMe, caller: CallerDep
) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.patch("/users/me/password", response_model=Message)
async def update_password_me(
    request: Request, body: UpdatePassword, caller: CallerDep
) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.get("/users/me", response_model=UserPublic)
async def read_user_me(request: Request, caller: CallerDep) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.delete("/users/me", response_model=Message)
async def delete_user_me(request: Request, caller: CallerDep) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.get("/users/{user_id}", response_model=UserPublic)
async def read_user_by_id(
    request: Request, user_id: UUID, caller: CallerDep
) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.patch("/users/{user_id}", response_model=UserPublic)
async def update_user(
    request: Request, user_id: UUID, body: UserUpdate, caller: CallerDep
) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)


@router.delete("/users/{user_id}", response_model=Message)
async def delete_user(request: Request, user_id: UUID, caller: CallerDep) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, caller)
