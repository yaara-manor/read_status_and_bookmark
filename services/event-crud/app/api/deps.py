from collections.abc import Generator
from typing import Annotated

from contracts import CALLER_HEADER, INTERNAL_KEY_HEADER, Caller, decode_caller
from fastapi import Depends, Header, HTTPException
from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]


def require_caller(
    internal_key: Annotated[str | None, Header(alias=INTERNAL_KEY_HEADER)] = None,
    caller_header: Annotated[str | None, Header(alias=CALLER_HEADER)] = None,
) -> Caller:
    if internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="invalid internal key")
    if not caller_header:
        raise HTTPException(status_code=401, detail="missing caller")
    try:
        caller = decode_caller(caller_header)
    except ValueError:
        raise HTTPException(status_code=401, detail="missing caller")
    if not caller.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return caller


CallerDep = Annotated[Caller, Depends(require_caller)]
