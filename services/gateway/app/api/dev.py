from contracts import DevUserCreate, UserPublic
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.config import settings
from app.forward import proxy

router = APIRouter(tags=["dev"])


@router.post("/dev/users", response_model=UserPublic)
async def create_user(request: Request, body: DevUserCreate) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, None)
