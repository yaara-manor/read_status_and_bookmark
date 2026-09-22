from fastapi import FastAPI

from app.api.routes.health import router

app = FastAPI()
app.include_router(router)
