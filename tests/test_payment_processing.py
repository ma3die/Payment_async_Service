import logging
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from core.exceptions import RetryableError, WebhookDeliveryError, WebhookRejectedError
from enums.payment import Currency, PaymentStatus
from models.payment import Payment
from schemas.messages import PaymentNewEvent
from services.delivery import deliver_payment
from services.payment_processor import PaymentProcessor
from services.retry import AttemptRunner, RetryPolicy


class MemorySession:
    def __init__(self, payment: Payment | None) -> None:
        self.payment = payment
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, model, payment_id, with_for_update: bool = False):
        if self.payment is None or self.payment.id != payment_id:
            return None
        return self.payment

    async def commit(self):
        self.commits += 1


class Gateway:
    def __init__(self, status: PaymentStatus = PaymentStatus.SUCCEEDED) -> None:
        self.status = status
        self.calls = 0

    async def authorize(self) -> PaymentStatus:
        self.calls += 1
        return self.status


class Webhooks:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.sent = []

    async def send(self, url: str, payload) -> None:
        if self.failures:
            self.failures -= 1
            raise WebhookDeliveryError("down")
        self.sent.append((url, payload))


def _payment() -> Payment:
    return Payment(
        id=uuid4(),
        amount=Decimal("15.00"),
        currency=Currency.USD,
        description="Заказ",
        payment_metadata={"order_id": "15"},
        status=PaymentStatus.PENDING,
        idempotency_key="key-15",
        webhook_url="https://client.test/hook",
    )


def _runner() -> AttemptRunner:
    return AttemptRunner(
        RetryPolicy(max_attempts=3, base_delay_seconds=0),
        retryable=(RetryableError,),
        sleep=_noop,
    )


async def _noop(delay: float) -> None:
    return None


@pytest.mark.asyncio
async def test_processor_authorizes_pending_payment_once():
    payment = _payment()
    session = MemorySession(payment)
    gateway = Gateway()
    webhooks = Webhooks()
    processor = PaymentProcessor(lambda: session, gateway, webhooks)

    snapshot = await processor.settle(payment.id)
    await processor.notify(snapshot)
    await processor.settle(payment.id)
    await processor.notify(snapshot)

    assert gateway.calls == 1
    assert payment.status is PaymentStatus.SUCCEEDED
    assert payment.processed_at is not None
    assert session.commits == 1
    assert len(webhooks.sent) == 2


@pytest.mark.asyncio
async def test_processor_missing_payment_is_not_retried_by_delivery():
    session = MemorySession(None)
    processor = PaymentProcessor(lambda: session, Gateway(), Webhooks())
    dead = []

    async def publish(event: PaymentNewEvent) -> None:
        dead.append(event)

    await deliver_payment(
        processor,
        PaymentNewEvent(payment_id=uuid4()),
        _runner(),
        publish,
    )

    assert dead == []


@pytest.mark.asyncio
async def test_delivery_moves_message_to_dlq_after_webhook_failures():
    payment = _payment()
    session = MemorySession(payment)
    gateway = Gateway()
    webhooks = Webhooks(failures=3)
    processor = PaymentProcessor(lambda: session, gateway, webhooks)
    dead = []

    async def publish(event: PaymentNewEvent) -> None:
        dead.append(event)

    await deliver_payment(
        processor,
        PaymentNewEvent(payment_id=payment.id),
        _runner(),
        publish,
    )

    assert gateway.calls == 1
    assert payment.status is PaymentStatus.SUCCEEDED
    assert len(dead) == 1
    assert dead[0].payment_id == payment.id
    assert webhooks.sent == []


@pytest.mark.asyncio
async def test_rejected_webhook_goes_to_dlq_without_retries():
    payment = _payment()
    calls = {"count": 0}

    class RejectingWebhooks:
        async def send(self, url: str, payload) -> None:
            calls["count"] += 1
            raise WebhookRejectedError("rejected")

    dead = []

    async def publish(event: PaymentNewEvent) -> None:
        dead.append(event)

    processor = PaymentProcessor(lambda: MemorySession(payment), Gateway(), RejectingWebhooks())
    await deliver_payment(processor, PaymentNewEvent(payment_id=payment.id), _runner(), publish)

    assert calls["count"] == 1
    assert len(dead) == 1


class FailingSession:
    def __init__(self) -> None:
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, model, payment_id, with_for_update: bool = False):
        self.calls += 1
        raise SQLAlchemyError("down")


@pytest.mark.asyncio
async def test_database_errors_go_to_dlq_without_calling_gateway(caplog):
    session = FailingSession()
    gateway = Gateway()
    processor = PaymentProcessor(lambda: session, gateway, Webhooks())
    dead = []

    async def publish(event: PaymentNewEvent) -> None:
        dead.append(event)

    with caplog.at_level(logging.ERROR):
        await deliver_payment(
            processor,
            PaymentNewEvent(payment_id=uuid4()),
            _runner(),
            publish,
        )

    assert session.calls == 3
    assert gateway.calls == 0
    assert len(dead) == 1
    assert "статус не записан" in caplog.text
