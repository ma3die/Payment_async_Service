from uuid import uuid4

import pytest

from enums.payment import OutboxStatus
from services.outbox_relay import ClaimedEvent, publish_one


class StoredEvent:
    def __init__(self, payload: dict) -> None:
        self.id = uuid4()
        self.payload = payload
        self.status = OutboxStatus.PENDING


class MemoryOutbox:
    def __init__(self, events: list[StoredEvent]) -> None:
        self.events = events

    async def claim(self) -> ClaimedEvent | None:
        for event in self.events:
            if event.status is OutboxStatus.PENDING:
                event.status = OutboxStatus.PUBLISHING
                return ClaimedEvent(id=event.id, payload=event.payload)
        return None

    async def mark_published(self, event_id) -> None:
        self._find(event_id).status = OutboxStatus.PUBLISHED

    async def release(self, event_id) -> None:
        self._find(event_id).status = OutboxStatus.PENDING

    async def mark_failed(self, event_id) -> None:
        self._find(event_id).status = OutboxStatus.FAILED

    def _find(self, event_id) -> StoredEvent:
        return next(event for event in self.events if event.id == event_id)


class ScriptedBroker:
    def __init__(self) -> None:
        self.sent: list = []
        self.failures_left = 0

    async def publish(self, message, **kwargs) -> None:
        if self.failures_left:
            self.failures_left -= 1
            raise ConnectionError("broker unavailable")
        self.sent.append(message.payment_id)


def _event(payment_id) -> StoredEvent:
    return StoredEvent({"payment_id": str(payment_id), "event_type": "payments.new"})


@pytest.mark.asyncio
async def test_failed_publish_keeps_previous_event_published():
    first_id = uuid4()
    second_id = uuid4()
    first = _event(first_id)
    second = _event(second_id)
    store = MemoryOutbox([first, second])
    broker = ScriptedBroker()

    assert await publish_one(broker, store) == 1
    broker.failures_left = 1
    with pytest.raises(ConnectionError):
        await publish_one(broker, store)

    assert first.status is OutboxStatus.PUBLISHED
    assert second.status is OutboxStatus.PENDING

    assert await publish_one(broker, store) == 1
    assert second.status is OutboxStatus.PUBLISHED
    assert broker.sent == [first_id, second_id]


@pytest.mark.asyncio
async def test_invalid_payload_does_not_block_the_next_event():
    broken = StoredEvent({"unexpected": True})
    payment_id = uuid4()
    valid = _event(payment_id)
    store = MemoryOutbox([broken, valid])
    broker = ScriptedBroker()

    assert await publish_one(broker, store) == 1
    assert broken.status is OutboxStatus.FAILED

    assert await publish_one(broker, store) == 1
    assert valid.status is OutboxStatus.PUBLISHED
    assert broker.sent == [payment_id]
