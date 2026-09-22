from contracts import UserCreate, UserCreated, UserMessage, UserPublic
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from app import crud
from app.api.deps import SessionDep, require_internal_key
from app.outbox import display_name, write_outbox

router = APIRouter(tags=["dev"], dependencies=[Depends(require_internal_key)])


class _DevUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str
    is_verified: bool = False


@router.post("/dev/users")
def create_user(session: SessionDep, user_in: _DevUserCreate) -> UserPublic:
    created = crud.create_user(
        session=session,
        user_create=UserCreate(
            email=user_in.email,
            password=user_in.password,
            full_name=user_in.full_name,
        ),
    )
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
    return UserPublic.model_validate(created.model_dump())
