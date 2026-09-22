import uuid
from datetime import UTC, datetime

from contracts import PerformerGenre, TicketAvailability
from sqlalchemy import CheckConstraint, Column, DateTime, Integer, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


class Venue(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    city: str = Field(max_length=255)
    country: str = Field(max_length=255)
    name: str = Field(max_length=255, unique=True)
    seat_map: list[int] = Field(sa_column=Column(ARRAY(Integer), nullable=False))


class Performer(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255)
    genre: PerformerGenre = Field(
        sa_column=Column(
            SAEnum(PerformerGenre, name="performer_genre", native_enum=True),
            nullable=False,
        )
    )
    description: str | None = Field(default=None, max_length=255)


class Event(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    time: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    venue_id: uuid.UUID = Field(foreign_key="venue.id", ondelete="RESTRICT")
    performer_id: uuid.UUID = Field(foreign_key="performer.id", ondelete="RESTRICT")
    owner_id: uuid.UUID
    creator: str = Field(max_length=255)


class Ticket(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("event_id", "row", "seat"),
        CheckConstraint("price >= 0"),
        CheckConstraint('"row" >= 0'),
        CheckConstraint("seat >= 0"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    event_id: uuid.UUID = Field(foreign_key="event.id", ondelete="CASCADE")
    user_id: uuid.UUID | None = Field(default=None)
    row: int = Field(ge=0)
    seat: int = Field(ge=0)
    price: float = Field(ge=0)
    availability: TicketAvailability = Field(
        sa_column=Column(
            SAEnum(TicketAvailability, name="ticket_availability", native_enum=True),
            nullable=False,
        )
    )


class EventReadLink(SQLModel, table=True):
    user_id: uuid.UUID = Field(primary_key=True)
    event_id: uuid.UUID = Field(
        foreign_key="event.id", primary_key=True, ondelete="CASCADE"
    )


class EventBookmarkLink(SQLModel, table=True):
    user_id: uuid.UUID = Field(primary_key=True)
    event_id: uuid.UUID = Field(
        foreign_key="event.id", primary_key=True, ondelete="CASCADE"
    )
