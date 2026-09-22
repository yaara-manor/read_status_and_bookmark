import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.core.db import engine
from app.models import Outbox, User
from tests.conftest import caller_headers

_PASSWORD = "password123"
_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$4RCPPnB4YNd3mDSHBbF7lQ$ujNIuvS1eeJ3ogu+jGf0xEovb08HZr+PruEH1yhbTIc"


def _email() -> str:
    return f"{uuid.uuid4().hex}@example.com"


def _insert_user(
    *,
    full_name: str | None = None,
    is_superuser: bool = False,
) -> User:
    with Session(engine) as session:
        user = User(
            email=_email(),
            full_name=full_name,
            hashed_password=_PASSWORD_HASH,
            is_superuser=is_superuser,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user


def _outbox_count() -> int:
    with Session(engine) as session:
        return session.exec(select(func.count()).select_from(Outbox)).one()


def _outbox_rows(user_id: uuid.UUID, event_name: str) -> list[Outbox]:
    with Session(engine) as session:
        rows = session.exec(select(Outbox).where(Outbox.event_name == event_name)).all()
        return [row for row in rows if str(row.payload["id"]) == str(user_id)]


def test_read_user_me(client: TestClient) -> None:
    user = _insert_user(full_name="Ada")
    response = client.get("/users/me", headers=caller_headers(user))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["email"] == user.email
    assert body["full_name"] == "Ada"
    assert "hashed_password" not in body


def test_list_users_forbidden_for_normal_caller(client: TestClient) -> None:
    user = _insert_user()
    response = client.get("/users", headers=caller_headers(user))
    assert response.status_code == 403
    assert response.json()["detail"] == "The user doesn't have enough privileges"


def test_admin_create_duplicate_email_is_409_and_writes_user_created_only_on_success(
    client: TestClient,
) -> None:
    admin = _insert_user(is_superuser=True)
    email = _email()
    headers = caller_headers(admin)
    created = client.post(
        "/users",
        json={"email": email, "password": _PASSWORD},
        headers=headers,
    )
    assert created.status_code == 200
    user_id = uuid.UUID(created.json()["id"])
    assert len(_outbox_rows(user_id, "UserCreated")) == 1
    before = _outbox_count()
    duplicate = client.post(
        "/users",
        json={"email": email, "password": _PASSWORD},
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "User with this email already exists"
    assert _outbox_count() == before


def test_display_name_change_writes_one_user_updated(client: TestClient) -> None:
    user = _insert_user()
    response = client.patch(
        "/users/me",
        json={"full_name": "Ada Lovelace"},
        headers=caller_headers(user),
    )
    assert response.status_code == 200
    rows = _outbox_rows(user.id, "UserUpdated")
    assert len(rows) == 1
    assert rows[0].payload["display_name"] == "Ada Lovelace"


def test_email_change_with_same_display_name_writes_nothing(
    client: TestClient,
) -> None:
    user = _insert_user(full_name="Ada")
    before = _outbox_count()
    response = client.patch(
        "/users/me",
        json={"email": _email()},
        headers=caller_headers(user),
    )
    assert response.status_code == 200
    assert _outbox_count() == before


def test_password_change_writes_nothing(client: TestClient) -> None:
    user = _insert_user()
    before = _outbox_count()
    response = client.patch(
        "/users/me/password",
        json={"current_password": _PASSWORD, "new_password": "newpassword1"},
        headers=caller_headers(user),
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password updated successfully"
    assert _outbox_count() == before


def test_delete_me_writes_user_deleted_and_removes_row(client: TestClient) -> None:
    user = _insert_user()
    response = client.delete("/users/me", headers=caller_headers(user))
    assert response.status_code == 200
    assert response.json()["message"] == "User deleted successfully"
    assert len(_outbox_rows(user.id, "UserDeleted")) == 1
    with Session(engine) as session:
        assert session.get(User, user.id) is None


def test_superuser_self_delete_writes_nothing(client: TestClient) -> None:
    user = _insert_user(is_superuser=True)
    before = _outbox_count()
    response = client.delete("/users/me", headers=caller_headers(user))
    assert response.status_code == 403
    assert (
        response.json()["detail"] == "Super users are not allowed to delete themselves"
    )
    assert _outbox_count() == before
    with Session(engine) as session:
        assert session.get(User, user.id) is not None
