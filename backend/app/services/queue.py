import json

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractQueue

from app.core.config import Settings, get_settings


class QueuePublisher:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def publish(self, routing_key: str, payload: dict, message_id: str) -> None:
        connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            queue = await declare_answer_queue(channel, self.settings.queue_name)
            body = {"event_type": routing_key, **payload}
            message = aio_pika.Message(
                body=json.dumps(body).encode("utf-8"),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=message_id,
            )
            await channel.default_exchange.publish(message, routing_key=queue.name)


async def declare_answer_queue(channel: AbstractChannel, queue_name: str) -> AbstractQueue:
    dlq_name = f"{queue_name}.dlq"
    await channel.declare_queue(dlq_name, durable=True)
    return await channel.declare_queue(
        queue_name,
        durable=True,
        arguments={"x-dead-letter-exchange": "", "x-dead-letter-routing-key": dlq_name},
    )
