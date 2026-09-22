from pathlib import Path

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.public import public_router
from app.core.config import settings

API_V1 = "/api/v1"
FRONTEND_DIR = Path(__file__).parent / "frontend"


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.FASTAPI_ENV != "development":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{API_V1}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_HOST],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=API_V1)
app.include_router(
    public_router(include_dev=settings.FASTAPI_ENV == "development"),
    prefix=API_V1,
)
if FRONTEND_DIR.is_dir():
    app.frontend("/", directory=FRONTEND_DIR)
