import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.db import engine
from app.models import User

_PASSWORD = "password123"
_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$4RCPPnB4YNd3mDSHBbF7lQ$ujNIuvS1eeJ3ogu+jGf0xEovb08HZr+PruEH1yhbTIc"


def _email() -> str:
    return f"{uuid.uuid4().hex}@example.com"


def _insert_user(
    *,
    email: str,
    full_name: str | None = None,
    is_superuser: bool = False,
) -> User:
    with Session(engine) as session:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=_PASSWORD_HASH,
            is_superuser=is_superuser,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user


def test_login_token_resolves_to_caller(client: TestClient) -> None:
    email = _email()
    user = _insert_user(email=email, full_name="Ada", is_superuser=True)
    login = client.post("/auth/login", json={"email": email, "password": _PASSWORD})
    assert login.status_code == 200
    response = client.post(
        "/internal/resolve-token",
        json={"token": login.json()["access_token"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["is_superuser"] is True
    assert body["display_name"] == "Ada"


def test_garbage_token_is_403(client: TestClient) -> None:
    response = client.post("/internal/resolve-token", json={"token": "not-a-token"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Could not validate credentials"


def test_inactive_user_token_is_400(client: TestClient) -> None:
    email = _email()
    user = _insert_user(email=email)
    login = client.post("/auth/login", json={"email": email, "password": _PASSWORD})
    assert login.status_code == 200
    with Session(engine) as session:
        row = session.get(User, user.id)
        assert row is not None
        row.is_active = False
        session.add(row)
        session.commit()
    response = client.post(
        "/internal/resolve-token",
        json={"token": login.json()["access_token"]},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"
