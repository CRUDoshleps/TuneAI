import asyncio

import pytest

from app import worker


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
