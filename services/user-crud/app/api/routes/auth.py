from datetime import timedelta

from contracts import (
    LoginRequest,
    Message,
    NewPassword,
    Token,
    UserCreate,
    UserCreated,
    UserMessage,
    UserPublic,
    UserRegister,
    UserUpdate,
)
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import crud
from app.api.deps import SessionDep, require_internal_key
from app.core import security
from app.core.config import settings
from app.email import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)
from app.outbox import display_name, write_outbox

router = APIRouter(prefix="/auth", dependencies=[Depends(require_internal_key)])


class _RecoveryEmail(BaseModel):
    email: str


@router.post("/login")
def login(session: SessionDep, body: LoginRequest) -> Token:
    user = crud.authenticate(session=session, email=body.email, password=body.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )


@router.post("/register")
def register(session: SessionDep, user_in: UserRegister) -> UserPublic:
    if crud.get_user_by_email(session=session, email=user_in.email):
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    created = crud.create_user(
        session=session,
        user_create=UserCreate.model_validate(user_in.model_dump()),
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
    return created


@router.post("/password-recovery")
def recover_password(session: SessionDep, body: _RecoveryEmail) -> Message:
    user = crud.get_user_by_email(session=session, email=body.email)
    if user:
        password_reset_token = generate_password_reset_token(email=body.email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=body.email, token=password_reset_token
        )
        send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return Message(
        message="If that email is registered, we sent a password recovery link"
    )


@router.post("/reset-password")
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = crud.get_user_by_email(session=session, email=email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    crud.update_user(
        session=session,
        db_user=user,
        user_in=UserUpdate(password=body.new_password),
    )
    return Message(message="Password updated successfully")
