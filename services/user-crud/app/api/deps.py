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


def require_internal_key(
    internal_key: Annotated[str | None, Header(alias=INTERNAL_KEY_HEADER)] = None,
) -> None:
    if internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="invalid internal key")


def require_caller(
    caller_header: Annotated[str | None, Header(alias=CALLER_HEADER)] = None,
) -> Caller:
    if not caller_header:
        raise HTTPException(status_code=401, detail="missing caller")
    try:
        caller = decode_caller(caller_header)
    except ValueError:
        raise HTTPException(status_code=401, detail="missing caller")
    if not caller.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return caller


def require_superuser(caller: Annotated[Caller, Depends(require_caller)]) -> Caller:
    if not caller.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return caller
