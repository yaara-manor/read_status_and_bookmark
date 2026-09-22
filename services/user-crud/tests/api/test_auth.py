import uuid

import pytest
from contracts import INTERNAL_KEY_HEADER
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.core.config import settings
from app.core.db import engine
from app.email import generate_password_reset_token
from app.models import Outbox, User

_PASSWORD = "password123"
# Argon2 hash of _PASSWORD. Login checks this without importing the hasher.
_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$4RCPPnB4YNd3mDSHBbF7lQ$ujNIuvS1eeJ3ogu+jGf0xEovb08HZr+PruEH1yhbTIc"
_RECOVERY_MESSAGE = "If that email is registered, we sent a password recovery link"


def _email() -> str:
    return f"{uuid.uuid4().hex}@example.com"


def _outbox_count() -> int:
    with Session(engine) as session:
        return session.exec(select(func.count()).select_from(Outbox)).one()


def _insert_user(*, email: str, is_active: bool = True) -> None:
    with Session(engine) as session:
        session.add(
            User(email=email, hashed_password=_PASSWORD_HASH, is_active=is_active)
        )
        session.commit()


def test_wrong_internal_key_is_401(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"email": _email(), "password": _PASSWORD},
        headers={INTERNAL_KEY_HEADER: "wrong-key"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal key"


def test_login_success_returns_bearer_token(client: TestClient) -> None:
    email = _email()
    _insert_user(email=email)
    response = client.post(
        "/auth/login",
        json={"email": email, "password": _PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_failure_is_400_and_writes_no_outbox(client: TestClient) -> None:
    email = _email()
    _insert_user(email=email)
    before = _outbox_count()
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "not-the-password"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect email or password"
    assert _outbox_count() == before


def test_login_inactive_user_is_400(client: TestClient) -> None:
    email = _email()
    _insert_user(email=email, is_active=False)
    response = client.post(
        "/auth/login",
        json={"email": email, "password": _PASSWORD},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"


def test_register_writes_user_created_outbox(client: TestClient) -> None:
    email = _email()
    response = client.post(
        "/auth/register",
        json={"email": email, "password": _PASSWORD},
    )
    assert response.status_code == 200
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).one()
        rows = session.exec(
            select(Outbox).where(Outbox.event_name == "UserCreated")
        ).all()
        match = [row for row in rows if str(row.payload["id"]) == str(user.id)]
        assert len(match) == 1
        payload = match[0].payload
        assert payload["display_name"] == email
        assert payload["is_superuser"] is False


def test_duplicate_register_is_400_and_adds_no_outbox_row(client: TestClient) -> None:
    email = _email()
    first = client.post(
        "/auth/register",
        json={"email": email, "password": _PASSWORD},
    )
    assert first.status_code == 200
    before = _outbox_count()
    second = client.post(
        "/auth/register",
        json={"email": email, "password": _PASSWORD},
    )
    assert second.status_code == 400
    assert (
        second.json()["detail"]
        == "The user with this email already exists in the system"
    )
    assert _outbox_count() == before


def test_password_recovery_unknown_email_returns_same_message(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[object] = []
    monkeypatch.setattr(
        "app.api.routes.auth.send_email", lambda **_kwargs: sent.append(_kwargs)
    )
    response = client.post(
        "/auth/password-recovery",
        json={"email": _email()},
    )
    assert response.status_code == 200
    assert response.json()["message"] == _RECOVERY_MESSAGE
    assert sent == []


def test_password_recovery_known_email_mail_disabled_returns_same_message(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", None)
    email = _email()
    _insert_user(email=email)
    response = client.post("/auth/password-recovery", json={"email": email})
    assert response.status_code == 200
    assert response.json()["message"] == _RECOVERY_MESSAGE


def test_password_recovery_known_email_sends_and_returns_same_message(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[str] = []

    def _send(
        _self: object,
        to: str | None = None,
        smtp: object = None,
        **_kwargs: object,
    ) -> str:
        if to is not None and smtp is not None:
            sent.append(to)
        return "ok"

    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "from@example.com")
    monkeypatch.setattr(settings, "EMAILS_FROM_NAME", "Box Office")
    monkeypatch.setattr("emails.message.Message.send", _send)
    email = _email()
    _insert_user(email=email)
    before = _outbox_count()
    response = client.post("/auth/password-recovery", json={"email": email})
    assert response.status_code == 200
    assert response.json()["message"] == _RECOVERY_MESSAGE
    assert sent == [email]
    assert _outbox_count() == before


def test_reset_password_unknown_email_is_400(client: TestClient) -> None:
    token = generate_password_reset_token(email=_email())
    response = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "newpassword1"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid token"


def test_reset_password_inactive_user_is_400(client: TestClient) -> None:
    email = _email()
    _insert_user(email=email, is_active=False)
    before_hash = _PASSWORD_HASH
    token = generate_password_reset_token(email=email)
    response = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "newpassword1"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).one()
        assert user.hashed_password == before_hash


def test_reset_password_updates_password(client: TestClient) -> None:
    email = _email()
    _insert_user(email=email)
    token = generate_password_reset_token(email=email)
    response = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "newpassword1"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password updated successfully"
    success = client.post(
        "/auth/login", json={"email": email, "password": "newpassword1"}
    )
    assert success.status_code == 200
    failure = client.post("/auth/login", json={"email": email, "password": _PASSWORD})
    assert failure.status_code == 400


def test_reset_password_bad_token_is_400_and_writes_no_outbox(
    client: TestClient,
) -> None:
    before = _outbox_count()
    response = client.post(
        "/auth/reset-password",
        json={"token": "not-a-token", "new_password": _PASSWORD},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid token"
    assert _outbox_count() == before
