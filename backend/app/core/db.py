from datetime import UTC, datetime

from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import EventCreate, Performer, PerformerGenre, User, UserCreate, Venue

engine = create_engine(str(settings.DATABASE_URL), pool_pre_ping=True)


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)
    venue = session.exec(select(Venue).where(Venue.name == "Main Hall")).first()
    if not venue:
        venue = Venue(
            name="Main Hall",
            city="Tel Aviv",
            country="Israel",
            seat_map=[4, 5, 5, 7],
        )
        performer = Performer(
            name="The Band",
            genre=PerformerGenre.MUSIC,
            description="Live music",
        )
        session.add(venue)
        session.add(performer)
        session.commit()
        crud.create_event(
            session=session,
            event_in=EventCreate(
                name="Opening Night",
                description="First show of the season",
                venue_id=venue.id,
                performer_id=performer.id,
                time=datetime(2026, 10, 1, 20, 0, tzinfo=UTC),
                price=25.0,
            ),
            owner_id=user.id,
        )
