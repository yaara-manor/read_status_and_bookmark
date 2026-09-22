from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.config import settings
from app.forward import proxy

router = APIRouter(tags=["dev"])


@router.post("/dev/users")
async def create_user(request: Request) -> Response:
    return await proxy(request, settings.USER_CRUD_URL, None)
