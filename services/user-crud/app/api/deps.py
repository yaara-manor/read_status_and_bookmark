from collections.abc import Generator
from typing import Annotated

from contracts import INTERNAL_KEY_HEADER
from fastapi import Depends, Header, HTTPException
from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]


def require_internal_key(
    internal_key: Annotated[str | None, Header(alias=INTERNAL_KEY_HEADER)] = None,
) -> None:
    if internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="invalid internal key")
