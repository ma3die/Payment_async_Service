from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.exceptions import PaymentNotFoundError, RetryableError
from enums.payment import Currency, PaymentStatus
from models.payment import Payment
from schemas.payment import WebhookPayload
from services.payment_gateway import SimulatedPaymentGateway
from services.webhook_sender import WebhookSender


@dataclass(frozen=True)
class PaymentSnapshot:
    payment_id: UUID
    status: PaymentStatus
    amount: Decimal
    currency: Currency
    webhook_url: str
    processed_at: datetime | None


class PaymentProcessor:
    """Переводит платёж из pending в итоговый статус и уведомляет клиента."""

    _db_attempts = 3

    def __init__(
            self,
            session_factory: async_sessionmaker[AsyncSession],
            gateway: SimulatedPaymentGateway,
            webhooks: WebhookSender,
    ) -> None:
        self._session_factory = session_factory
        self._gateway = gateway
        self._webhooks = webhooks

    async def settle(self, payment_id: UUID) -> PaymentSnapshot:
        """Один вызов шлюза и запись статуса. Повтор касается только commit, не шлюза."""
        snapshot = await self._call_db(lambda: self._load(payment_id))
        if snapshot.status is not PaymentStatus.PENDING:
            return snapshot
        status = await self._gateway.authorize()
        return await self._call_db(lambda: self._save_status(payment_id, status))

    async def notify(self, snapshot: PaymentSnapshot) -> None:
        await self._webhooks.send(snapshot.webhook_url, self._payload(snapshot))

    async def _call_db(self, operation):
        last_error: SQLAlchemyError | None = None
        for _ in range(self._db_attempts):
            try:
                return await operation()
            except SQLAlchemyError as exc:
                last_error = exc
        if last_error is None:
            raise RetryableError("Не удалось записать статус платежа")
        raise last_error

    async def _load(self, payment_id: UUID) -> PaymentSnapshot:
        async with self._session_factory() as session:
            payment = await session.get(Payment, payment_id)
            if payment is None:
                raise PaymentNotFoundError()
            return self._snapshot(payment)

    async def _save_status(self, payment_id: UUID, status: PaymentStatus) -> PaymentSnapshot:
        async with self._session_factory() as session:
            payment = await session.get(Payment, payment_id, with_for_update=True)
            if payment is None:
                raise PaymentNotFoundError()
            if payment.status is PaymentStatus.PENDING:
                payment.status = status
                payment.processed_at = datetime.now(UTC)
                await session.commit()
            return self._snapshot(payment)

    @staticmethod
    def _snapshot(payment: Payment) -> PaymentSnapshot:
        return PaymentSnapshot(
            payment_id=payment.id,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            webhook_url=payment.webhook_url,
            processed_at=payment.processed_at,
        )

    @staticmethod
    def _payload(snapshot: PaymentSnapshot) -> WebhookPayload:
        processed_at = snapshot.processed_at
        if processed_at is None:
            raise RetryableError("У платежа нет времени обработки")
        return WebhookPayload(
            payment_id=snapshot.payment_id,
            status=snapshot.status,
            amount=snapshot.amount,
            currency=snapshot.currency,
            processed_at=processed_at,
        )
