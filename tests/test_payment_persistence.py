import asyncio

import pytest
from sqlalchemy import func, select, text

from core.exceptions import IdempotencyConflictError
from enums.payment import Currency, PaymentStatus
from models.outbox import OutboxEvent
from models.payment import Payment
from schemas.payment import PaymentCreate
from services.payment_service import PaymentService
from services.request_hash import payment_request_hash


def _create(amount: str = "10.00") -> PaymentCreate:
    return PaymentCreate(
        amount=amount,
        currency=Currency.RUB,
        description="Заказ",
        metadata={"order_id": "1"},
        webhook_url="https://client.test/hook",
    )


def _payment(data: PaymentCreate, idempotency_key: str) -> Payment:
    return Payment(
        amount=data.amount,
        currency=data.currency,
        description=data.description,
        payment_metadata=data.metadata,
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key,
        request_hash=payment_request_hash(data),
        webhook_url=str(data.webhook_url),
    )


async def _wait_until_blocked(factory) -> None:
    for _ in range(100):
        async with factory() as session:
            waiting = await session.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() "
                    "AND pid <> pg_backend_pid() "
                    "AND wait_event_type = 'Lock'"
                )
            )
        if waiting:
            return
        await asyncio.sleep(0.05)
    pytest.fail("Вторая транзакция не дождалась блокировки уникального индекса")


async def _insert_and_hold(factory, data: PaymentCreate, idempotency_key: str, inserted: asyncio.Event) -> None:
    async with factory() as session:
        payment = _payment(data, idempotency_key)
        session.add(payment)
        await session.flush()
        session.add(PaymentService._new_event(payment))
        await session.flush()
        inserted.set()
        await _wait_until_blocked(factory)
        await session.commit()


async def _count(factory, model) -> int:
    async with factory() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def _run_while_first_insert_is_open(db, operation):
    inserted = asyncio.Event()
    holder = asyncio.create_task(_insert_and_hold(db, _create("10.00"), "order-1", inserted))
    try:
        await asyncio.wait_for(inserted.wait(), timeout=5)
        return await operation()
    finally:
        await holder


@pytest.mark.asyncio
async def test_concurrent_same_body_keeps_one_payment_and_one_outbox(db):
    async def create():
        async with db() as session:
            return await PaymentService(session).create_payment(_create("10.00"), "order-1")

    payment = await _run_while_first_insert_is_open(db, create)

    assert payment.idempotency_key == "order-1"
    assert await _count(db, Payment) == 1
    assert await _count(db, OutboxEvent) == 1


@pytest.mark.asyncio
async def test_concurrent_different_body_returns_conflict_and_keeps_one_row(db):
    async def create_other_body():
        async with db() as session:
            await PaymentService(session).create_payment(_create("11.00"), "order-1")

    with pytest.raises(IdempotencyConflictError):
        await _run_while_first_insert_is_open(db, create_other_body)

    assert await _count(db, Payment) == 1
    assert await _count(db, OutboxEvent) == 1
