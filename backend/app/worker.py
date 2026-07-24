import asyncio
import json

import aio_pika
import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal, init_db
from app.metrics import ANSWERS_COMPLETED, ANSWERS_FAILED
from app.models import AnswerStatusEnum
from app.services.outbox import ANSWER_UPLOADED, get_pending_events, mark_failed, mark_published
from app.services.processing import process_answer_uploaded
from app.services.queue import QueuePublisher, declare_answer_queue


configure_logging()
settings = get_settings()
logger = structlog.get_logger("tuneai.worker")


async def publish_outbox_once() -> int:
    publisher = QueuePublisher(settings)
    published = 0
    with SessionLocal() as db:
        events = get_pending_events(db, limit=50)
        for event in events:
            try:
                await publisher.publish(event.event_type, event.payload, event.id)
                mark_published(db, event)
                db.commit()
                published += 1
            except Exception as exc:
                db.rollback()
                mark_failed(db, event, str(exc))
                db.commit()
                logger.exception("outbox_publish_failed", event_id=event.id)
    return published


async def publisher_loop() -> None:
    while True:
        await publish_outbox_once()
        await asyncio.sleep(2)


async def consume_answers() -> None:
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=4)
        queue = await declare_answer_queue(channel, settings.queue_name)
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process(requeue=False):
                    payload = json.loads(message.body.decode("utf-8"))
                    event_type = payload.get("event_type") or ANSWER_UPLOADED
                    if event_type != ANSWER_UPLOADED and "answer_id" not in payload:
                        logger.warning("unknown_event", payload=payload)
                        continue
                    await handle_answer_message(payload)


async def handle_answer_message(payload: dict) -> None:
    answer_id = payload["answer_id"]
    with SessionLocal() as db:
        answer = await process_answer_uploaded(db, answer_id=answer_id)
        if answer.status == AnswerStatusEnum.completed:
            ANSWERS_COMPLETED.inc()
        elif answer.status == AnswerStatusEnum.failed:
            ANSWERS_FAILED.inc()


async def main() -> None:
    init_db()
    await asyncio.gather(publisher_loop(), consume_answers())


if __name__ == "__main__":
    asyncio.run(main())
