import uuid
from typing import Annotated, Any

from contracts import (
    Caller,
    Message,
    UpdatePassword,
    UserCreate,
    UserCreated,
    UserDeleted,
    UserMessage,
    UserPublic,
    UsersPublic,
    UserUpdate,
    UserUpdated,
    UserUpdateMe,
)
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import (
    SessionDep,
    require_caller,
    require_internal_key,
    require_superuser,
)
from app.core.security import get_password_hash, verify_password
from app.models import User
from app.outbox import display_name, write_outbox

router = APIRouter(dependencies=[Depends(require_internal_key)])
CallerDep = Annotated[Caller, Depends(require_caller)]
_NOT_FOUND = "User not found"
_MISSING_ID = "The user with this id does not exist in the system"


def _public(user: User) -> UserPublic:
    return UserPublic.model_validate(user.model_dump())


def _user_or_404(session: SessionDep, user_id: uuid.UUID, detail: str) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=detail)
    return user


def _reject_duplicate_email(
    session: SessionDep, email: str | None, user_id: uuid.UUID
) -> None:
    if not email:
        return
    existing = crud.get_user_by_email(session=session, email=email)
    if existing and existing.id != user_id:
        raise HTTPException(
            status_code=409, detail="User with this email already exists"
        )


def _save(session: SessionDep, user: User, data: dict[str, Any]) -> User:
    password = data.pop("password", None)
    before = display_name(user)
    user.sqlmodel_update(data)
    if password:
        user.hashed_password = get_password_hash(password)
    session.add(user)
    if display_name(user) != before:
        write_outbox(
            session,
            UserMessage(
                event_name="UserUpdated",
                payload=UserUpdated(id=user.id, display_name=display_name(user)),
            ),
        )
    session.commit()
    session.refresh(user)
    return user


def _delete(session: SessionDep, user: User, caller: Caller) -> Message:
    if user.is_superuser and user.id == caller.id:
        raise HTTPException(
            status_code=403,
            detail="Super users are not allowed to delete themselves",
        )
    user_id = user.id
    session.delete(user)
    write_outbox(
        session,
        UserMessage(event_name="UserDeleted", payload=UserDeleted(id=user_id)),
    )
    session.commit()
    return Message(message="User deleted successfully")


@router.get("/users", dependencies=[Depends(require_superuser)])
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> UsersPublic:
    count = session.exec(select(func.count()).select_from(User)).one()
    users = session.exec(
        select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    ).all()
    return UsersPublic(data=[_public(user) for user in users], count=count)


@router.post("/users", dependencies=[Depends(require_superuser)])
def create_user(session: SessionDep, user_in: UserCreate) -> UserPublic:
    if crud.get_user_by_email(session=session, email=user_in.email):
        raise HTTPException(
            status_code=409, detail="User with this email already exists"
        )
    created = crud.create_user(session=session, user_create=user_in)
    write_outbox(
        session,
        UserMessage(
            event_name="UserCreated",
            payload=UserCreated(
                id=created.id,
                display_name=display_name(created),
                is_superuser=created.is_superuser,
            ),
        ),
    )
    session.commit()
    session.refresh(created)
    return _public(created)


@router.patch("/users/me")
def update_user_me(
    session: SessionDep, user_in: UserUpdateMe, caller: CallerDep
) -> UserPublic:
    user = _user_or_404(session, caller.id, _NOT_FOUND)
    _reject_duplicate_email(session, user_in.email, user.id)
    return _public(user=_save(session, user, user_in.model_dump(exclude_unset=True)))


@router.patch("/users/me/password")
def update_password_me(
    session: SessionDep, body: UpdatePassword, caller: CallerDep
) -> Message:
    user = _user_or_404(session, caller.id, _NOT_FOUND)
    verified, _ = verify_password(body.current_password, user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password cannot be the same as the current one",
        )
    user.hashed_password = get_password_hash(body.new_password)
    session.add(user)
    session.commit()
    return Message(message="Password updated successfully")


@router.get("/users/me")
def read_user_me(session: SessionDep, caller: CallerDep) -> UserPublic:
    return _public(_user_or_404(session, caller.id, _NOT_FOUND))


@router.delete("/users/me")
def delete_user_me(session: SessionDep, caller: CallerDep) -> Message:
    return _delete(session, _user_or_404(session, caller.id, _NOT_FOUND), caller)


@router.get("/users/{user_id}")
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, caller: CallerDep
) -> UserPublic:
    user = session.get(User, user_id)
    if user is not None and user.id == caller.id:
        return _public(user)
    if not caller.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    if user is None:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return _public(user)


@router.patch("/users/{user_id}", dependencies=[Depends(require_superuser)])
def update_user(
    session: SessionDep, user_id: uuid.UUID, user_in: UserUpdate
) -> UserPublic:
    user = _user_or_404(session, user_id, _MISSING_ID)
    _reject_duplicate_email(session, user_in.email, user.id)
    return _public(_save(session, user, user_in.model_dump(exclude_unset=True)))


@router.delete("/users/{user_id}", dependencies=[Depends(require_superuser)])
def delete_user(session: SessionDep, caller: CallerDep, user_id: uuid.UUID) -> Message:
    return _delete(session, _user_or_404(session, user_id, _NOT_FOUND), caller)
