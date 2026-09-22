from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

STREAM = "user-events"
DEAD_STREAM = "user-events-dead"
CONSUMER_GROUP = "event-crud"


class UserCreated(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    display_name: str
    is_superuser: bool


class UserUpdated(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    display_name: str


class UserDeleted(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID


_PAYLOADS: dict[str, type[UserCreated | UserUpdated | UserDeleted]] = {
    "UserCreated": UserCreated,
    "UserUpdated": UserUpdated,
    "UserDeleted": UserDeleted,
}


class UserMessage(BaseModel):
    event_name: Literal["UserCreated", "UserUpdated", "UserDeleted"]
    payload: UserCreated | UserUpdated | UserDeleted

    @model_validator(mode="before")
    @classmethod
    def match_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        name = data.get("event_name")
        model = _PAYLOADS.get(name) if isinstance(name, str) else None
        payload = data.get("payload")
        if model is None:
            return data
        if isinstance(payload, model):
            return data
        if isinstance(payload, BaseModel):
            payload = payload.model_dump()
        try:
            parsed = model.model_validate(payload)
        except ValidationError as exc:
            raise ValueError("payload does not match event_name") from exc
        return {**data, "payload": parsed}


def dump_message(message: UserMessage) -> str:
    return message.model_dump_json()


def load_message(data: str) -> UserMessage:
    try:
        return UserMessage.model_validate_json(data)
    except ValidationError as exc:
        raise ValueError("invalid message") from exc
