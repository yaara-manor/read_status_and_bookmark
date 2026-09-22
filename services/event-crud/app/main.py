from fastapi import FastAPI

from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router

app = FastAPI()
app.include_router(health_router)
app.include_router(events_router)
