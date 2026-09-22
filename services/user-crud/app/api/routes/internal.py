import uuid

import jwt
from contracts import Caller
from fastapi import APIRouter, Depends, HTTPException
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel
from sqlmodel import Session

from app.api.deps import SessionDep, require_internal_key
from app.core import security
from app.core.config import settings
from app.models import User
from app.outbox import display_name

router = APIRouter(dependencies=[Depends(require_internal_key)])


class _TokenBody(BaseModel):
    token: str


def _caller_for_token(session: Session, token: str) -> Caller:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        user_id = uuid.UUID(str(payload["sub"]))
    except InvalidTokenError, ValueError, KeyError:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return Caller(
        id=user.id,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        display_name=display_name(user),
    )


@router.post("/internal/resolve-token")
def resolve_token(session: SessionDep, body: _TokenBody) -> Caller:
    return _caller_for_token(session, body.token)
