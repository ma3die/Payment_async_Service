from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from core.exceptions import (
    IdempotencyConflictError,
    InvalidIdempotencyKeyError,
    PaymentNotFoundError,
)
from enums.payment import Currency, PaymentStatus
from models.outbox import OutboxEvent
from models.payment import Payment
from schemas.payment import PaymentCreate
from services.payment_service import PaymentService
from services.request_hash import payment_request_hash


class QueryResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    def __init__(self, existing: Payment | None = None) -> None:
        self.existing = existing
        self.added: list = []
        self.committed = False

    def add(self, obj) -> None:
        self.added.append(obj)

    async def execute(self, statement) -> QueryResult:
        return QueryResult(self.existing)

    async def flush(self) -> None:
        for obj in self.added:
            if isinstance(obj, Payment) and obj.id is None:
                obj.id = uuid4()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.added.clear()

    async def refresh(self, obj) -> None:
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)

    async def get(self, model, payment_id):
        if self.existing is not None and self.existing.id == payment_id:
            return self.existing
        return None


def _create(amount: str = "10.00", metadata: dict | None = None) -> PaymentCreate:
    return PaymentCreate(
        amount=amount,
        currency=Currency.RUB,
        description="Заказ",
        metadata={"b": 1, "a": 2} if metadata is None else metadata,
        webhook_url="https://client.test/hook",
    )


def _existing(amount: str = "10.00") -> Payment:
    data = _create(amount)
    return Payment(
        id=uuid4(),
        amount=Decimal(amount),
        currency=Currency.RUB,
        description=data.description,
        payment_metadata=data.metadata,
        status=PaymentStatus.PENDING,
        idempotency_key="order-1",
        request_hash=payment_request_hash(data),
        webhook_url=str(data.webhook_url),
        created_at=datetime.now(UTC),
    )


def test_request_hash_ignores_metadata_key_order():
    left = payment_request_hash(_create(metadata={"a": 2, "b": 1}))
    right = payment_request_hash(_create(metadata={"b": 1, "a": 2}))
    assert left == right


@pytest.mark.asyncio
async def test_create_payment_writes_payment_and_outbox():
    session = FakeSession()
    payment = await PaymentService(session).create_payment(_create(), "  order-1  ")

    assert session.committed is True
    assert payment.idempotency_key == "order-1"
    assert payment.request_hash == payment_request_hash(_create())
    assert any(isinstance(obj, OutboxEvent) for obj in session.added)


@pytest.mark.asyncio
async def test_same_key_and_body_returns_existing_payment():
    existing = _existing()
    session = FakeSession(existing)

    found = await PaymentService(session).create_payment(_create(), "order-1")

    assert found is existing
    assert session.added == []
    assert session.committed is False


@pytest.mark.asyncio
async def test_same_key_with_different_body_returns_conflict():
    session = FakeSession(_existing("10.00"))

    with pytest.raises(IdempotencyConflictError):
        await PaymentService(session).create_payment(_create("11.00"), "order-1")


@pytest.mark.asyncio
async def test_blank_idempotency_key_is_rejected():
    with pytest.raises(InvalidIdempotencyKeyError):
        await PaymentService(FakeSession()).create_payment(_create(), "   ")


@pytest.mark.asyncio
async def test_get_missing_payment():
    with pytest.raises(PaymentNotFoundError):
        await PaymentService(FakeSession()).get_payment(uuid4())
