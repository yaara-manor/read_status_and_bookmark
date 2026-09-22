from contracts import (
    LoginRequest,
    Message,
    NewPassword,
    RecoveryEmail,
    Token,
    UserPublic,
    UserRegister,
)
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.config import settings
from app.forward import proxy

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(request: Request, body: LoginRequest) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, None)


@router.post("/register", response_model=UserPublic)
async def register(request: Request, body: UserRegister) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, None)


@router.post("/password-recovery", response_model=Message)
async def recover_password(request: Request, body: RecoveryEmail) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, None)


@router.post("/reset-password", response_model=Message)
async def reset_password(request: Request, body: NewPassword) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, None)
