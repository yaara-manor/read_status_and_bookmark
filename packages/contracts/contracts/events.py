from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class PerformerGenre(str, Enum):
    MUSIC = "MUSIC"
    SPORT = "SPORT"
    THEATRE = "THEATRE"
    CIRCUS = "CIRCUS"


class TicketAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"


class EventBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class EventCreate(EventBase):
    venue_id: UUID
    performer_id: UUID
    time: datetime
    price: float = Field(ge=0)


class EventUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    time: datetime | None = None
    performer_id: UUID | None = None


class TicketPublic(BaseModel):
    id: UUID
    row: int
    seat: int
    price: float
    availability: TicketAvailability
    user_id: UUID | None = None


class EventPublic(EventBase):
    id: UUID
    owner_id: UUID
    venue_id: UUID
    performer_id: UUID
    time: datetime
    created_at: datetime | None = None
    creator: str
    is_read: bool = False
    is_bookmarked: bool = False


class EventDetail(EventPublic):
    tickets: list[TicketPublic]


class EventBookmarkUpdate(BaseModel):
    is_bookmarked: bool


class EventsPublic(BaseModel):
    data: list[EventPublic]
    count: int
