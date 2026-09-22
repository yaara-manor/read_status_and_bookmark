import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.dev import router as dev_router
from app.api.routes.health import router as health_router
from app.api.routes.internal import router as internal_router
from app.api.routes.users import router as users_router
from app.core.config import settings
from app.publisher import run_publisher


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    threading.Thread(target=run_publisher, name="user-events", daemon=True).start()
    yield


app = FastAPI(lifespan=_lifespan)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(internal_router)
if settings.FASTAPI_ENV == "development":
    app.include_router(dev_router)
