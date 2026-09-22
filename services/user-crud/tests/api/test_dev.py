import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.db import engine
from app.models import Outbox, User

_PASSWORD = "password123"


def _email() -> str:
    return f"{uuid.uuid4().hex}@example.com"


def test_dev_create_user_returns_user_and_writes_user_created(
    client: TestClient,
) -> None:
    email = _email()
    response = client.post(
        "/dev/users",
        json={
            "email": email,
            "password": _PASSWORD,
            "full_name": "Dev User",
            "is_verified": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == email
    assert body["full_name"] == "Dev User"
    assert "hashed_password" not in body
    user_id = body["id"]
    with Session(engine) as session:
        rows = session.exec(
            select(Outbox).where(Outbox.event_name == "UserCreated")
        ).all()
        match = [row for row in rows if str(row.payload["id"]) == user_id]
        assert len(match) == 1
        assert match[0].payload["display_name"] == "Dev User"
        assert match[0].payload["is_superuser"] is False
        assert session.get(User, uuid.UUID(user_id)) is not None
