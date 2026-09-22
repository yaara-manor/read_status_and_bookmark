import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.consumer import run_consumer


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    threading.Thread(target=run_consumer, name="user-events", daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(health_router)
app.include_router(events_router)
