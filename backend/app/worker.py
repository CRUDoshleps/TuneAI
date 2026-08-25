import asyncio
import json

import aio_pika
import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal, init_db
from app.metrics import ANSWERS_COMPLETED, ANSWERS_FAILED
from app.models import AnswerStatusEnum, MaterialIndexStatusEnum
from app.services.outbox import ANSWER_UPLOADED, MATERIAL_UPLOADED, get_pending_events, mark_failed, mark_published
from app.services.processing import process_answer_uploaded
from app.services.queue import QueuePublisher, declare_answer_queue
from app.services.rag import index_material


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
        try:
            await publish_outbox_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("outbox_loop_failed")
        await asyncio.sleep(2)


async def _consume_answers_once() -> None:
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
                    if event_type not in {ANSWER_UPLOADED, MATERIAL_UPLOADED}:
                        logger.warning("unknown_event", payload=payload)
                        continue
                    if event_type == ANSWER_UPLOADED:
                        if "answer_id" not in payload:
                            logger.warning("unknown_event", payload=payload)
                            continue
                        await handle_answer_message(payload)
                    else:
                        if "material_id" not in payload:
                            logger.warning("unknown_event", payload=payload)
                            continue
                        await handle_material_message(payload)


async def consume_answers() -> None:
    while True:
        try:
            await _consume_answers_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("consumer_connection_failed", retry_in_seconds=2)
            await asyncio.sleep(2)


async def handle_answer_message(payload: dict) -> None:
    answer_id = payload["answer_id"]
    with SessionLocal() as db:
        answer = await process_answer_uploaded(db, answer_id=answer_id)
        if answer.status == AnswerStatusEnum.completed:
            ANSWERS_COMPLETED.inc()
        elif answer.status == AnswerStatusEnum.failed:
            ANSWERS_FAILED.inc()


async def handle_material_message(payload: dict) -> None:
    material_id = payload["material_id"]
    with SessionLocal() as db:
        material = await index_material(db, material_id=material_id)
        if material.index_status == MaterialIndexStatusEnum.failed:
            logger.warning("material_index_failed", material_id=material.id, error=material.index_error)


async def main() -> None:
    settings.validate_production()
    init_db()
    await asyncio.gather(publisher_loop(), consume_answers())


if __name__ == "__main__":
    asyncio.run(main())
