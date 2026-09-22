from uuid import UUID

import pytest
from contracts import Caller, decode_caller, encode_caller


def test_caller_round_trip_keeps_unicode_display_name() -> None:
    caller = Caller(
        id=UUID("12345678-1234-5678-1234-567812345678"),
        is_active=True,
        is_superuser=False,
        display_name="José",
    )
    assert decode_caller(encode_caller(caller)) == caller


def test_decode_caller_garbage_raises() -> None:
    with pytest.raises(ValueError):
        decode_caller("!!!not-base64!!!")
