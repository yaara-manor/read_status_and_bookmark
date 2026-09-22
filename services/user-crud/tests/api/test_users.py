import uuid

from contracts import CALLER_HEADER, Caller, encode_caller
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.core.db import engine
from app.models import Outbox, User
from app.outbox import display_name


def caller_headers(user: User) -> dict[str, str]:
    caller = Caller(
        id=user.id,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        display_name=display_name(user),
    )
    return {CALLER_HEADER: encode_caller(caller)}


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


def test_missing_caller_is_401(client: TestClient) -> None:
    response = client.get("/users/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "missing caller"


def test_invalid_caller_is_401(client: TestClient) -> None:
    response = client.get("/users/me", headers={CALLER_HEADER: "%%%"})
    assert response.status_code == 401
    assert response.json()["detail"] == "missing caller"


def test_inactive_caller_is_400(client: TestClient) -> None:
    caller = Caller(
        id=uuid.uuid4(),
        is_active=False,
        is_superuser=False,
        display_name="Inactive",
    )
    response = client.get("/users/me", headers={CALLER_HEADER: encode_caller(caller)})
    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"


def test_read_user_me_missing_row_is_404(client: TestClient) -> None:
    caller = Caller(
        id=uuid.uuid4(),
        is_active=True,
        is_superuser=False,
        display_name="Missing",
    )
    response = client.get("/users/me", headers={CALLER_HEADER: encode_caller(caller)})
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_read_users_returns_count_for_superuser(client: TestClient) -> None:
    admin = _insert_user(is_superuser=True)
    response = client.get("/users", headers=caller_headers(admin))
    assert response.status_code == 200
    body = response.json()
    with Session(engine) as session:
        count = session.exec(select(func.count()).select_from(User)).one()
    assert body["count"] == count
    assert len(body["data"]) == min(count, 100)


def test_update_me_duplicate_email_is_409(client: TestClient) -> None:
    first = _insert_user()
    second = _insert_user()
    before = _outbox_count()
    response = client.patch(
        "/users/me",
        json={"email": first.email},
        headers=caller_headers(second),
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "User with this email already exists"
    assert _outbox_count() == before


def test_update_password_wrong_current_is_400(client: TestClient) -> None:
    user = _insert_user()
    response = client.patch(
        "/users/me/password",
        json={"current_password": "wrongpassword", "new_password": "newpassword1"},
        headers=caller_headers(user),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect password"


def test_update_password_same_value_is_400(client: TestClient) -> None:
    user = _insert_user()
    response = client.patch(
        "/users/me/password",
        json={"current_password": _PASSWORD, "new_password": _PASSWORD},
        headers=caller_headers(user),
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "New password cannot be the same as the current one"
    )


def test_read_user_by_id_self_returns_public(client: TestClient) -> None:
    user = _insert_user()
    response = client.get(f"/users/{user.id}", headers=caller_headers(user))
    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_read_user_by_id_other_is_403(client: TestClient) -> None:
    user = _insert_user()
    other = _insert_user()
    response = client.get(f"/users/{other.id}", headers=caller_headers(user))
    assert response.status_code == 403
    assert response.json()["detail"] == "The user doesn't have enough privileges"


def test_read_user_by_id_missing_is_404_for_superuser(client: TestClient) -> None:
    admin = _insert_user(is_superuser=True)
    response = client.get(f"/users/{uuid.uuid4()}", headers=caller_headers(admin))
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_read_user_by_id_other_is_200_for_superuser(client: TestClient) -> None:
    admin = _insert_user(is_superuser=True)
    other = _insert_user()
    response = client.get(f"/users/{other.id}", headers=caller_headers(admin))
    assert response.status_code == 200
    assert response.json()["email"] == other.email


def test_update_user_sets_password_and_duplicate_email_is_409(
    client: TestClient,
) -> None:
    admin = _insert_user(is_superuser=True)
    target = _insert_user()
    other = _insert_user()
    headers = caller_headers(admin)
    updated = client.patch(
        f"/users/{target.id}",
        json={"full_name": "Updated Name", "password": "newpassword1"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Updated Name"
    rows = _outbox_rows(target.id, "UserUpdated")
    assert len(rows) == 1
    login = client.post(
        "/auth/login", json={"email": target.email, "password": "newpassword1"}
    )
    assert login.status_code == 200
    before = _outbox_count()
    duplicate = client.patch(
        f"/users/{target.id}",
        json={"email": other.email},
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "User with this email already exists"
    assert _outbox_count() == before


def test_update_user_missing_is_404(client: TestClient) -> None:
    admin = _insert_user(is_superuser=True)
    response = client.patch(
        f"/users/{uuid.uuid4()}",
        json={"full_name": "Nobody"},
        headers=caller_headers(admin),
    )
    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "The user with this id does not exist in the system"
    )


def test_delete_user_removes_row(client: TestClient) -> None:
    admin = _insert_user(is_superuser=True)
    target = _insert_user()
    response = client.delete(f"/users/{target.id}", headers=caller_headers(admin))
    assert response.status_code == 200
    assert response.json()["message"] == "User deleted successfully"
    assert len(_outbox_rows(target.id, "UserDeleted")) == 1
    with Session(engine) as session:
        assert session.get(User, target.id) is None


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
