from contracts import DevUserCreate, UserCreate, UserPublic
from fastapi import APIRouter, Depends

from app import crud
from app.api.deps import SessionDep, require_internal_key
from app.api.mount import mount_catalog

router = APIRouter(dependencies=[Depends(require_internal_key)])


def create_user(session: SessionDep, user_in: DevUserCreate) -> UserPublic:
    created = crud.create_user(
        session=session,
        user_create=UserCreate(
            email=user_in.email,
            password=user_in.password,
            full_name=user_in.full_name,
        ),
    )
    return UserPublic.model_validate(created.model_dump())


mount_catalog(
    router,
    {"create_user": create_user},
    service="user",
    tag="dev",
)
