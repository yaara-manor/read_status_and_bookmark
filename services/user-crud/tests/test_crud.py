import uuid

from pwdlib.hashers.bcrypt import BcryptHasher
from sqlmodel import Session

from app import crud
from app.core.db import engine
from app.core.security import verify_password
from app.models import User

_PASSWORD = "password123"


def test_authenticate_unknown_email_returns_none() -> None:
    with Session(engine) as session:
        assert (
            crud.authenticate(
                session=session,
                email=f"{uuid.uuid4().hex}@example.com",
                password=_PASSWORD,
            )
            is None
        )


def test_authenticate_rehash_replaces_bcrypt_hash() -> None:
    email = f"{uuid.uuid4().hex}@example.com"
    bcrypt_hash = BcryptHasher().hash(_PASSWORD)
    with Session(engine) as session:
        user = User(email=email, hashed_password=bcrypt_hash)
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id

        authenticated = crud.authenticate(
            session=session, email=email, password=_PASSWORD
        )
        assert authenticated is not None
        assert authenticated.id == user_id
        assert authenticated.hashed_password != bcrypt_hash
        verified, _ = verify_password(_PASSWORD, authenticated.hashed_password)
        assert verified is True
