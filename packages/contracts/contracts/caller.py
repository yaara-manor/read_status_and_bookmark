import base64
import binascii
from uuid import UUID

from pydantic import BaseModel, ValidationError

INTERNAL_KEY_HEADER = "X-Internal-Key"
CALLER_HEADER = "X-Caller"


class Caller(BaseModel):
    id: UUID
    is_active: bool
    is_superuser: bool
    display_name: str


def encode_caller(caller: Caller) -> str:
    return base64.b64encode(caller.model_dump_json().encode()).decode()


def decode_caller(value: str) -> Caller:
    try:
        raw = base64.b64decode(value, validate=True)
        return Caller.model_validate_json(raw)
    except (binascii.Error, ValidationError) as exc:
        raise ValueError("invalid caller") from exc
