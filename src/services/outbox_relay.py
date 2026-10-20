import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from faststream.rabbit import RabbitBroker
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from broker.topology import payments_exchange
from config import logger, settings
from db.session import async_session_maker
from enums.payment import OutboxStatus
from models.outbox import OutboxEvent
from schemas.messages import PaymentNewEvent

STALE_PUBLISHING_AFTER = timedelta(seconds=30)


@dataclass(frozen=True)
class ClaimedEvent:
    id: UUID
    payload: dict


class OutboxStore(Protocol):
    async def claim(self) -> ClaimedEvent | None:
        """Забирает одно событие, не удерживая блокировку на время публикации."""

    async def mark_published(self, event_id: UUID) -> None:
        """Ставит published после confirm брокера."""

    async def release(self, event_id: UUID) -> None:
        """Возвращает событие в pending, если брокер его не принял."""

    async def mark_failed(self, event_id: UUID) -> None:
        """Уводит битый payload из головы очереди."""


class SqlOutboxStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def claim(self) -> ClaimedEvent | None:
        async with self._session_factory() as session, session.begin():
            await self._release_stale(session)
            event = await self._lock_next(session)
            if event is None:
                return None
            event.status = OutboxStatus.PUBLISHING
            return ClaimedEvent(id=event.id, payload=dict(event.payload))

    async def mark_published(self, event_id: UUID) -> None:
        await self._set_status(event_id, OutboxStatus.PUBLISHED, published_at=datetime.now(UTC))

    async def release(self, event_id: UUID) -> None:
        await self._set_status(event_id, OutboxStatus.PENDING)

    async def mark_failed(self, event_id: UUID) -> None:
        await self._set_status(event_id, OutboxStatus.FAILED)

    async def _release_stale(self, session: AsyncSession) -> None:
        stale_before = datetime.now(UTC) - STALE_PUBLISHING_AFTER
        await session.execute(
            update(OutboxEvent)
            .where(
                OutboxEvent.status == OutboxStatus.PUBLISHING,
                OutboxEvent.updated_at < stale_before,
            )
            .values(status=OutboxStatus.PENDING, updated_at=datetime.now(UTC))
        )

    async def _lock_next(self, session: AsyncSession) -> OutboxEvent | None:
        statement = (
            select(OutboxEvent)
            .where(OutboxEvent.status == OutboxStatus.PENDING)
            .order_by(OutboxEvent.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def _set_status(self, event_id: UUID, status: OutboxStatus, published_at: datetime | None = None) -> None:
        values: dict = {"status": status, "updated_at": datetime.now(UTC)}
        if published_at is not None:
            values["published_at"] = published_at
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(OutboxEvent)
                .where(
                    OutboxEvent.id == event_id,
                    OutboxEvent.status == OutboxStatus.PUBLISHING,
                )
                .values(**values)
            )


async def publish_one(broker: RabbitBroker, store: OutboxStore) -> int:
    """Публикует одно событие. Confirm брокера происходит до отметки published."""
    claimed = await store.claim()
    if claimed is None:
        return 0
    try:
        message = PaymentNewEvent.model_validate(claimed.payload)
    except ValidationError:
        await store.mark_failed(claimed.id)
        logger.error("Событие outbox %s отброшено: битый payload", claimed.id)
        return 1
    try:
        await broker.publish(
            message,
            exchange=payments_exchange,
            routing_key=settings.rabbit.PAYMENTS_ROUTING_KEY,
            persist=True,
        )
    except Exception:
        await store.release(claimed.id)
        raise
    await store.mark_published(claimed.id)
    return 1


async def run_outbox_relay(broker: RabbitBroker, stop: asyncio.Event) -> None:
    """Читает outbox, пока процесс не получит сигнал остановки."""
    store = SqlOutboxStore(async_session_maker)
    while not stop.is_set():
        published = await _publish_safely(broker, store)
        if published:
            continue
        await _wait(stop)


async def _publish_safely(broker: RabbitBroker, store: OutboxStore) -> int:
    try:
        return await publish_one(broker, store)
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось опубликовать событие outbox")
        return 0


async def _wait(stop: asyncio.Event) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=settings.outbox.OUTBOX_POLL_INTERVAL_SECONDS)
    except TimeoutError:
        return
