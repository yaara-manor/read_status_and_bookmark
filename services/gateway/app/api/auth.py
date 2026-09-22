from contracts import LoginRequest, NewPassword, UserRegister
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.config import settings
from app.forward import proxy

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(request: Request, body: LoginRequest) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, None)


@router.post("/register")
async def register(request: Request, body: UserRegister) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, None)


@router.post("/password-recovery")
async def recover_password(request: Request) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, None)


@router.post("/reset-password")
async def reset_password(request: Request, body: NewPassword) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, None)
