from collections.abc import Awaitable, Callable

from config import logger, settings
from core.exceptions import PaymentNotFoundError, WebhookRejectedError
from schemas.messages import PaymentNewEvent
from services.payment_processor import PaymentProcessor
from services.retry import AttemptRunner


async def deliver_payment(
        processor: PaymentProcessor,
        event: PaymentNewEvent,
        runner: AttemptRunner,
        publish_dead_letter: Callable[[PaymentNewEvent], Awaitable[None]],
) -> None:
    """Пишет статус один раз и повторяет только доставку webhook."""
    try:
        snapshot = await processor.settle(event.payment_id)
    except PaymentNotFoundError:
        logger.error("Платёж %s не найден, сообщение пропущено", event.payment_id)
        return
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось зафиксировать статус платежа %s", event.payment_id)
        await _dead_letter(publish_dead_letter, event, "статус не записан")
        return

    try:
        delivered = await runner.run(lambda: processor.notify(snapshot))
    except WebhookRejectedError:
        await _dead_letter(publish_dead_letter, event, "webhook отвергнут")
        return

    if delivered:
        return
    await _dead_letter(publish_dead_letter, event, f"исчерпаны {settings.retry.RETRY_MAX_ATTEMPTS} попытки")


async def _dead_letter(
        publish_dead_letter: Callable[[PaymentNewEvent], Awaitable[None]],
        event: PaymentNewEvent,
        reason: str,
) -> None:
    await publish_dead_letter(event)
    logger.error("Платёж %s отправлен в DLQ: %s", event.payment_id, reason)
