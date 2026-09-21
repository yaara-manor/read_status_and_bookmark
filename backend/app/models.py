import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import EmailStr
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class EventReadLink(SQLModel, table=True):
    user_id: uuid.UUID = Field(
        foreign_key="user.id", primary_key=True, ondelete="CASCADE"
    )
    event_id: uuid.UUID = Field(
        foreign_key="event.id", primary_key=True, ondelete="CASCADE"
    )


class EventBookmarkLink(SQLModel, table=True):
    user_id: uuid.UUID = Field(
        foreign_key="user.id", primary_key=True, ondelete="CASCADE"
    )
    event_id: uuid.UUID = Field(
        foreign_key="event.id", primary_key=True, ondelete="CASCADE"
    )


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    events: list[Event] = Relationship(back_populates="owner", cascade_delete=True)
    read_events: list[Event] = Relationship(
        back_populates="readers", link_model=EventReadLink
    )
    bookmarked_events: list[Event] = Relationship(
        back_populates="bookmarked_by", link_model=EventBookmarkLink
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


class PerformerGenre(str, Enum):
    MUSIC = "MUSIC"
    SPORT = "SPORT"
    THEATRE = "THEATRE"
    CIRCUS = "CIRCUS"


class TicketAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"


class Venue(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    city: str = Field(max_length=255)
    country: str = Field(max_length=255)
    name: str = Field(max_length=255)
    seat_map: list[int] = Field(sa_column=Column(ARRAY(Integer), nullable=False))
    events: list[Event] = Relationship(back_populates="venue")


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
    events: list[Event] = Relationship(back_populates="performer")


class EventBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class EventCreate(EventBase):
    venue_id: uuid.UUID
    performer_id: uuid.UUID
    time: datetime
    price: float = Field(ge=0)


class EventUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    time: datetime | None = None
    performer_id: uuid.UUID | None = None


class Event(EventBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    time: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    venue_id: uuid.UUID = Field(foreign_key="venue.id", ondelete="RESTRICT")
    performer_id: uuid.UUID = Field(foreign_key="performer.id", ondelete="RESTRICT")
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    venue: Venue | None = Relationship(back_populates="events")
    performer: Performer | None = Relationship(back_populates="events")
    owner: User | None = Relationship(back_populates="events")
    tickets: list[Ticket] = Relationship(back_populates="event", cascade_delete=True)
    readers: list[User] = Relationship(
        back_populates="read_events", link_model=EventReadLink
    )
    bookmarked_by: list[User] = Relationship(
        back_populates="bookmarked_events", link_model=EventBookmarkLink
    )


class Ticket(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("event_id", "row", "seat"),
        CheckConstraint("price >= 0"),
        CheckConstraint('"row" >= 0'),
        CheckConstraint("seat >= 0"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    event_id: uuid.UUID = Field(foreign_key="event.id", ondelete="CASCADE")
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    row: int = Field(ge=0)
    seat: int = Field(ge=0)
    price: float = Field(ge=0)
    availability: TicketAvailability = Field(
        sa_column=Column(
            SAEnum(TicketAvailability, name="ticket_availability", native_enum=True),
            nullable=False,
        )
    )
    event: Event | None = Relationship(back_populates="tickets")


class TicketPublic(SQLModel):
    id: uuid.UUID
    row: int
    seat: int
    price: float
    availability: TicketAvailability
    user_id: uuid.UUID | None = None


class EventPublic(EventBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    venue_id: uuid.UUID
    performer_id: uuid.UUID
    time: datetime
    created_at: datetime | None = None
    creator: str
    is_read: bool = False
    is_bookmarked: bool = False

    @classmethod
    def from_event(
        cls,
        event: Event,
        *,
        is_read: bool = False,
        is_bookmarked: bool = False,
    ) -> EventPublic:
        owner = event.owner
        creator = (owner.full_name or owner.email) if owner else ""
        return cls.model_validate(
            event,
            update={
                "creator": creator,
                "is_read": is_read,
                "is_bookmarked": is_bookmarked,
            },
        )


class EventDetail(EventPublic):
    tickets: list[TicketPublic]


class EventBookmarkUpdate(SQLModel):
    is_bookmarked: bool


class EventsPublic(SQLModel):
    data: list[EventPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
