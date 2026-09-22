from contracts import UserCreate, UserCreated, UserMessage
from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import User
from app.outbox import display_name, write_outbox

engine = create_engine(str(settings.DATABASE_URL), pool_pre_ping=True)


def init_db(session: Session) -> None:
    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if user:
        return
    created = crud.create_user(
        session=session,
        user_create=UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        ),
    )
    write_outbox(
        session,
        UserMessage(
            event_name="UserCreated",
            payload=UserCreated(
                id=created.id,
                display_name=display_name(created),
                is_superuser=True,
            ),
        ),
    )
    session.commit()
