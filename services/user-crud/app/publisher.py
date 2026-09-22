import asyncio
import logging

from contracts import STREAM, UserMessage, dump_message
from redis import Redis
from redis.exceptions import RedisError
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.db import engine
from app.models import Outbox, get_datetime_utc

logger = logging.getLogger(__name__)


def publish_pending(redis: Redis) -> int:
    published = 0
    with Session(engine) as session:
        rows = session.exec(
            select(Outbox)
            .where(col(Outbox.published_at).is_(None))
            .order_by(col(Outbox.created_at))
        ).all()
        for row in rows:
            message = UserMessage.model_validate(
                {"event_name": row.event_name, "payload": row.payload}
            )
            redis.xadd(STREAM, {"data": dump_message(message)})
            row.published_at = get_datetime_utc()
            session.commit()
            published += 1
    return published


async def run_publisher() -> None:
    client = Redis.from_url(settings.REDIS_URL)
    while True:
        try:
            publish_pending(client)
        except RedisError:
            logger.exception("Redis refused the connection")
        await asyncio.sleep(1)
