from contracts import UserMessage
from sqlmodel import Session

from app.models import Outbox, User


def display_name(user: User) -> str:
    if user.full_name:
        return user.full_name
    return user.email


def write_outbox(session: Session, message: UserMessage) -> None:
    session.add(
        Outbox(
            event_name=message.event_name,
            payload=message.payload.model_dump(mode="json"),
        )
    )
