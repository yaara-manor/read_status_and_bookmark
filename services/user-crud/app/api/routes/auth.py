import logging
from datetime import timedelta

from contracts import (
    LoginRequest,
    Message,
    NewPassword,
    RecoveryEmail,
    Token,
    UserCreate,
    UserPublic,
    UserRegister,
    UserUpdate,
)
from fastapi import APIRouter, Depends, HTTPException

from app import crud
from app.api.deps import SessionDep, require_internal_key
from app.api.mount import mount_catalog
from app.core import security
from app.core.config import settings
from app.email import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_internal_key)])


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
    return UserPublic.model_validate(created.model_dump())


def recover_password(session: SessionDep, body: RecoveryEmail) -> Message:
    user = crud.get_user_by_email(session=session, email=body.email)
    if user:
        password_reset_token = generate_password_reset_token(email=body.email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=body.email, token=password_reset_token
        )
        try:
            send_email(
                email_to=user.email,
                subject=email_data.subject,
                html_content=email_data.html_content,
            )
        except Exception:
            logger.exception("password recovery email failed")
    return Message(
        message="If that email is registered, we sent a password recovery link"
    )


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


mount_catalog(
    router,
    {
        "login": login,
        "register": register,
        "recover_password": recover_password,
        "reset_password": reset_password,
    },
    service="user",
    tag="auth",
)
