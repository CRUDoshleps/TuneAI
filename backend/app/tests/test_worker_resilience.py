import asyncio
import json

import pytest

from app import worker
from app.core.config import Settings
from app.services.queue import QueuePublisher


@pytest.mark.asyncio
async def test_consumer_retries_after_initial_broker_failure(monkeypatch):
    attempts = 0
    retry_delays: list[int] = []

    async def fake_consume_once() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("broker is still starting")
        raise asyncio.CancelledError

    async def fake_sleep(delay: int) -> None:
        retry_delays.append(delay)

    monkeypatch.setattr(worker, "_consume_answers_once", fake_consume_once)
    monkeypatch.setattr(worker.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await worker.consume_answers()

    assert attempts == 2
    assert retry_delays == [2]


@pytest.mark.asyncio
async def test_queue_publisher_includes_event_type_in_message_body(monkeypatch):
    published: dict[str, object] = {}

    class FakeExchange:
        async def publish(self, message, routing_key: str) -> None:
            published["body"] = json.loads(message.body.decode("utf-8"))
            published["routing_key"] = routing_key

    class FakeChannel:
        default_exchange = FakeExchange()

        async def declare_queue(self, name: str, durable: bool, arguments: dict | None = None):
            return type("Queue", (), {"name": name})()

    class FakeConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def channel(self):
            return FakeChannel()

    async def fake_connect_robust(url: str):
        return FakeConnection()

    monkeypatch.setattr("app.services.queue.aio_pika.connect_robust", fake_connect_robust)

    publisher = QueuePublisher(Settings(rabbitmq_url="amqp://example", queue_name="queue"))
    await publisher.publish("material.uploaded", {"material_id": "m1"}, "event-1")

    assert published["routing_key"] == "queue"
    assert published["body"] == {"event_type": "material.uploaded", "material_id": "m1"}
