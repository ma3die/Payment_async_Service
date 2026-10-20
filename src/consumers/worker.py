import asyncio
from dataclasses import dataclass, field

import httpx
from faststream import FastStream

from broker.rabbit import broker, declare_topology
from broker.topology import dead_letter_exchange, payments_exchange, payments_queue
from config import settings
from core.exceptions import RetryableError
from db.session import async_session_maker
from schemas.messages import PaymentNewEvent
from services.delivery import deliver_payment
from services.outbox_relay import run_outbox_relay
from services.payment_gateway import SimulatedPaymentGateway
from services.payment_processor import PaymentProcessor
from services.retry import AttemptRunner, RetryPolicy
from services.webhook_sender import WebhookSender

app = FastStream(broker)


@dataclass
class ConsumerState:
    client: httpx.AsyncClient | None = None
    processor: PaymentProcessor | None = None
    relay_task: asyncio.Task | None = None
    stop_relay: asyncio.Event = field(default_factory=asyncio.Event)


state = ConsumerState()


@app.on_startup
async def build_processor() -> None:
    state.client = httpx.AsyncClient(timeout=settings.webhook.WEBHOOK_TIMEOUT_SECONDS)
    state.processor = PaymentProcessor(
        session_factory=async_session_maker,
        gateway=SimulatedPaymentGateway(),
        webhooks=WebhookSender(state.client),
    )


@app.after_startup
async def start_relay() -> None:
    await declare_topology()
    state.relay_task = asyncio.create_task(run_outbox_relay(broker, state.stop_relay))


@app.on_shutdown
async def stop_relay() -> None:
    state.stop_relay.set()
    if state.relay_task is not None:
        await state.relay_task


@app.after_shutdown
async def close_client() -> None:
    if state.client is not None:
        await state.client.aclose()


@broker.subscriber(payments_queue, payments_exchange)
async def consume_new_payment(event: PaymentNewEvent) -> None:
    if state.processor is None:
        raise RuntimeError("Consumer ещё не готов")
    runner = _attempt_runner()
    await deliver_payment(state.processor, event, runner, _publish_dead_letter)


def _attempt_runner() -> AttemptRunner:
    policy = RetryPolicy(
        max_attempts=settings.retry.RETRY_MAX_ATTEMPTS,
        base_delay_seconds=settings.retry.RETRY_BASE_DELAY_SECONDS,
    )
    return AttemptRunner(policy, retryable=(RetryableError,))


async def _publish_dead_letter(event: PaymentNewEvent) -> None:
    await broker.publish(
        event,
        exchange=dead_letter_exchange,
        routing_key=settings.rabbit.PAYMENTS_ROUTING_KEY,
        persist=True,
    )


if __name__ == "__main__":
    asyncio.run(app.run())
