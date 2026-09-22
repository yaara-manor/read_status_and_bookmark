from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.forward import get_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> bool:
    user_url = f"{settings.USER_CRUD_URL.rstrip('/')}/health"
    event_url = f"{settings.EVENT_CRUD_URL.rstrip('/')}/health"
    try:
        healthy = get_status(user_url) == 200 and get_status(event_url) == 200
    except HTTPException:
        raise HTTPException(status_code=503, detail="Service unavailable") from None
    if healthy:
        return True
    raise HTTPException(status_code=503, detail="Service unavailable")
