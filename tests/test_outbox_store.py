import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from enums.payment import OutboxStatus
from models.outbox import OutboxEvent
from services.outbox_relay import SqlOutboxStore


def _event(status: OutboxStatus, age: timedelta) -> OutboxEvent:
    moment = datetime.now(UTC) - age
    return OutboxEvent(
        event_type="payments.new",
        payload={"payment_id": str(uuid4()), "event_type": "payments.new"},
        status=status,
        created_at=moment,
        updated_at=moment,
    )


async def _status(factory, event_id) -> OutboxStatus:
    async with factory() as session:
        saved = await session.get(OutboxEvent, event_id)
        return saved.status


@pytest.mark.asyncio
async def test_parallel_claims_take_different_events(db):
    async with db() as session:
        session.add(_event(OutboxStatus.PENDING, timedelta(seconds=2)))
        session.add(_event(OutboxStatus.PENDING, timedelta(seconds=1)))
        await session.commit()

    store = SqlOutboxStore(db)
    first, second = await asyncio.gather(store.claim(), store.claim())

    assert first is not None
    assert second is not None
    assert first.id != second.id
    assert await _status(db, first.id) is OutboxStatus.PUBLISHING
    assert await _status(db, second.id) is OutboxStatus.PUBLISHING


@pytest.mark.asyncio
async def test_claim_reopens_only_stale_publishing(db):
    fresh = _event(OutboxStatus.PUBLISHING, timedelta(seconds=1))
    stale = _event(OutboxStatus.PUBLISHING, timedelta(seconds=31))
    async with db() as session:
        session.add_all([fresh, stale])
        await session.commit()
        fresh_id = fresh.id
        stale_id = stale.id

    claimed = await SqlOutboxStore(db).claim()

    assert claimed is not None
    assert claimed.id == stale_id
    assert await _status(db, fresh_id) is OutboxStatus.PUBLISHING
    assert await _status(db, stale_id) is OutboxStatus.PUBLISHING


@pytest.mark.asyncio
async def test_mark_published_does_not_touch_row_returned_to_pending(db):
    event = _event(OutboxStatus.PENDING, timedelta(seconds=1))
    async with db() as session:
        session.add(event)
        await session.commit()
        event_id = event.id

    store = SqlOutboxStore(db)
    claimed = await store.claim()
    assert claimed.id == event_id

    async with db() as session:
        saved = await session.scalar(select(OutboxEvent).where(OutboxEvent.id == event_id))
        saved.status = OutboxStatus.PENDING
        await session.commit()

    await store.mark_published(event_id)

    async with db() as session:
        saved = await session.get(OutboxEvent, event_id)
        assert saved.status is OutboxStatus.PENDING
        assert saved.published_at is None
